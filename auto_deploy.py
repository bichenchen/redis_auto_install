#!/bin/python3

import argparse
from string import Template
import math
import random
import pymysql

inventory_tmplate = 'inventory_template.ini'
inventory = 'inventory.ini'
# max_sharding_size = 10  # GB
sharding_num_per_host = 12  # 每个主机固定是12个分片，每个分配最大8GB

## mysql args
host = "10.21.177.182"
user = "xdb_plus"
pwd = "xdbplus"
port = 3366
db = "redis_xdb_plus"


def operate_db(sql):
    try:
        con = pymysql.connect(host=host,
                              user=user,
                              port=port,
                              password=pwd,
                              database=db,
                              cursorclass=pymysql.cursors.DictCursor)
        cur = con.cursor()
        cur.execute(sql)
        out = cur.fetchall()
        return (out)
    except Exception as err:
        print("execute {sql} error:{err}".format(sql=sql,
                                                 err=err))
        exit(2)


def get_cluster_info(flow_instance_id):
    sql = "select * from cluster_order_info where flow_instance_id={0}".format(order_id)
    out = operate_db(sql)
    if out:
        info = out[0]
        return info
    else:
        print("no cluster order info for id {0}".format(order_id))
        exit(2)


parser = argparse.ArgumentParser(prog=None,
                                 usage=None,
                                 epilog=None,
                                 parents=[],
                                 formatter_class=argparse.HelpFormatter,
                                 prefix_chars='-',
                                 fromfile_prefix_chars=None,
                                 argument_default=None,
                                 conflict_handler='error',
                                 add_help=True)
parser.add_argument('--order_id', '-id', help="Redis申请工单ID，如若指定此参数则只需给定-MI和-SI即可")
parser.add_argument('--master_iplist', '-MI', help="部署redis的主机,逗号分隔")
parser.add_argument('--slave_iplist', '-SI', help="部署redis的主机,逗号分隔")
# parser.add_argument('--dataSize', '-D', help="redis 数据量大小，单位为GB，用于计算redis分片数量", type=int)
parser.add_argument('--name', '-N', help="cluster name,业务给定的关键字，并以此关键字进行命名bns,将-替换为_")
parser.add_argument('--owner', '-O', help="申请人")
parser.add_argument('--manager', '-M', help="直属leader")
parser.add_argument('--project_op', '-op', help="项目op")
parser.add_argument('--depart', '-D', help="部门")
# parser.add_argument('--groupMail', '-G', help="业务邮箱组",default="none")
parser.add_argument('--storage_type', '-T', help="使用类型", choices=['cache', 'storage'], default='catche')
parser.add_argument('--maxmemory_policy', '-P', help="Redis的最大淘汰策略",
                    choices=['noeviction', 'volatile-lru', 'allkeys-lru'], default='volatile-lru')
parser.add_argument('--note', '-B', help="备注")
args = parser.parse_args()
# print(vars(args))
order_id = args.order_id
master_iplist_ = args.master_iplist
slave_iplist_ = args.slave_iplist
if order_id:  # 如果指定order_id则只需给定ip
    if not master_iplist_ or not slave_iplist_:
        print("Error args:must give -MI and -SI")
        exit(2)
    info = get_cluster_info(order_id)
    order_id = info['id']
    name = info['cluster_name']
    bns_name_prex = name.replace('_', '-')
    owner = info['applicant']
    manager = info['manager']
    depart = info['department']
    product_line = ''  # 目前redis没有区分产品线
    op = info['project_op']
    storage_type = info['usage_type']
    maxmemory_policy = info['max_memory_policy']
    note = info['usage_note']
    app_white_list_bns = info['white_list_bns']
    app_white_list_ip = info['white_list_ip']
    if app_white_list_bns == 'null':
        app_white_list_bns = ''
    else:
        app_white_list_bns = eval(app_white_list_bns)
        app_white_list_bns = '\n'.join(app_white_list_bns)
    if app_white_list_ip == 'null':
        app_white_list_ip = ''
    else:
        app_white_list_ip = eval(app_white_list_ip)
        app_white_list_ip = '\n'.join(app_white_list_ip)
else:
    order_id = 0
    op = ''
    owner = args.owner
    manager = args.manager
    depart = args.depart
    maxmemory_policy = args.maxmemory_policy
    note = args.note
    storage_type = args.storage_type
    app_white_list_bns=''
    app_white_list_ip=''
    # group_mail=args.groupMail
    # data_size = args.dataSize
    name = args.name
    if name:
        if '-' in name:
            print("ERROR: invalit arg {0} should't contain '-'".format(name))
            print(parser.print_help())
            exit()
        else:
            bns_name_prex = name.replace('_', '-')
    args_dict = vars(args)  # convert from namespace to dict
    for arg in args_dict:
        if arg != 'order_id' and not args_dict[arg]:
            print('***************************************')
            print("ERROR: {0} muster be given if --order_id not given".format(arg))
            print(parser.print_help())
            exit()
master_ips, slave_ips = [], []
for i in master_iplist_.split(','):
    master_ips.append(i)
for i in slave_iplist_.split(','):
    slave_ips.append(i)


def redis_sharding_policy_():
    ips = []
    # 此分片策略基于一主一从设计的,将主库平摊到不同的主机
    redis_master_items = []
    redis_slave_items = []
    host_num = len(ips)  # redis主机的个数
    host_indexes = [i for i in range(host_num)]  # redis主机的下标，0~host_num-1
    # 向下取整
    # sharding_num = math.ceil(data_size / max_sharding_size)
    sharding_num = 12
    # 将master均摊到不同的主机
    cnt = 1
    redis_port = 7000
    for i in range(sharding_num):  # index从0到sharding_num-1
        master_inventory_hostname = 'm{cnt}'.format(cnt=cnt)
        slave_inventory_hostname = 's{cnt}'.format(cnt=cnt)
        master_host_index = i % host_num  # 取余获取部署master的主机的下标
        # host_indexes_copy=host_indexes.copy()
        # other_host_indexes=host_indexes_copy.remove(master_host_index) #其余的主机的下标，随机选择一台用于部署slave
        master_host = ips[master_host_index]
        # slave_host_index=random.choice(other_host_indexes)
        # slave_host=ips[slave_host_index]
        hosts_copy = ips.copy()
        del (hosts_copy[master_host_index])  # 删除部署主库的ip
        slave_host = random.choice(hosts_copy)  # 从其余的主机随机选一个部署从库
        redis_master_item = "{master_inventory_hostname} ansible_host={master_host} " \
                            "redis_port={redis_port}".format(master_inventory_hostname=master_inventory_hostname,
                                                             master_host=master_host,
                                                             redis_port=redis_port)
        redis_slave_item = "{slave_inventory_hostname} ansible_host={slave_host} " \
                           "redis_port={redis_port} master_host=" \
                           "{master_inventory_hostname}".format(slave_inventory_hostname=slave_inventory_hostname,
                                                                slave_host=slave_host,
                                                                redis_port=redis_port,
                                                                master_inventory_hostname=master_inventory_hostname)
        redis_master_items.append(redis_master_item)
        redis_slave_items.append(redis_slave_item)
        cnt += 1
        redis_port += 1
    return (redis_master_items, redis_slave_items)


def redis_sharding_policy():
    # 将主库部署在同一机房，从库部署在另一机房
    redis_master_items = []
    redis_slave_items = []
    cnt_total = 1
    for master_host in master_ips:
        cnt = 1
        redis_port = 7000
        for i in range(sharding_num_per_host):
            master_inventory_hostname = 'm{cnt}'.format(cnt=cnt_total)
            redis_master_item = "{master_inventory_hostname} ansible_host={master_host} " \
                                "redis_port={redis_port}".format(master_inventory_hostname=master_inventory_hostname,
                                                                 master_host=master_host,
                                                                 redis_port=redis_port)
            redis_master_items.append(redis_master_item)
            cnt += 1
            redis_port += 1
            cnt_total += 1
    cnt_total = 1
    for slave_host in slave_ips:
        cnt = 1
        redis_port = 7000
        for i in range(sharding_num_per_host):
            master_inventory_hostname = 'm{cnt}'.format(cnt=cnt_total)
            slave_inventory_hostname = 's{cnt}'.format(cnt=cnt_total)
            redis_slave_item = "{slave_inventory_hostname} ansible_host={slave_host} " \
                               "redis_port={redis_port} master_host=" \
                               "{master_inventory_hostname}".format(slave_inventory_hostname=slave_inventory_hostname,
                                                                    slave_host=slave_host,
                                                                    redis_port=redis_port,
                                                                    master_inventory_hostname=master_inventory_hostname)

            redis_slave_items.append(redis_slave_item)
            cnt += 1
            redis_port += 1
            cnt_total += 1
    return (redis_master_items, redis_slave_items)


def render_inventory():
    iplist = '\n'.join(master_ips + slave_ips)
    redis_master_items, redis_slave_items = redis_sharding_policy()
    redis_master_items = '\n'.join(redis_master_items)
    redis_slave_items = '\n'.join(redis_slave_items)
    with open(inventory_tmplate, 'r') as out:
        out_con = out.readlines()
        out_con_ = Template(''.join(out_con)).safe_substitute(nutcracker_hosts=iplist,
                                                              sentinel_hosts=iplist,
                                                              redis_master_items=redis_master_items,
                                                              redis_slave_items=redis_slave_items,
                                                              owner=owner,
                                                              manager=manager,
                                                              depart=depart,
                                                              storage_type=storage_type,
                                                              maxmemory_policy=maxmemory_policy,
                                                              note=note,
                                                              bns_name_prex=bns_name_prex,
                                                              app_white_list_bns=app_white_list_bns,
                                                              app_white_list_ip=app_white_list_ip,
                                                              op=op,
                                                              order_id=order_id,
                                                              name=name)
    out_con_format = [line + '\n' for line in out_con_.split('\n')]
    with open(inventory, 'w') as infile:
        in_con = infile
        in_con.writelines(out_con_format)


def do_deploy():
    print("*******************************************")
    print("Please check {inventory} for sentinel_port and whitelist and then execute:\n "
          "ansible-playbook -i inventory.ini deploy.yml".format(inventory=inventory))


def main():
    render_inventory()
    do_deploy()


if __name__ == '__main__':
    main()
