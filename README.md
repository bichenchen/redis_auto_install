## description
for deploying redis cluster,including redis server、sentinel server、nutcracker
## enviroment
- python3
- ansible 2.8

## usage
on contol host

1、configure redis sharding under redis hosts given
- ./auto_deploy.py for help
- example:
./auto_deploy.py --iplist=1.1.1.1,1.1.1.2,1.1.1.3 -N test -D 60 

./auto_deploy.py -id 8734 -MI 1.1.1.1 -SI 1.1.1.1

2、 check inventory.ini and configure whiltelist

3、 execute
- deploy redis cluster

ansible-playbook -i inventory.ini deploy.yml
- deploy single service，example

ansible-playbook -i inventory.ini deploy.yml --tags="redis"

ansible-playbook -i inventory.ini deploy.yml --tags="sentinel,nutcracker"
