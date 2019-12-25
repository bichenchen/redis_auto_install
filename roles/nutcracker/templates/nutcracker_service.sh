#!/bin/bash

NUTCRACKER_PORT={{ nutcracker_port }}
SENTINEL_BNS="{{ groups.sentinel_bns|join(',') }}"
SENTINEL_PORT={{ sentinel_port }}
STATUS_PORT={{ sentinel_status_port }}
time=$(date "+%Y-%m-%d %H:%M:%S")
cd {{ base_dir }}
function start(){
    echo "${time} starting..nutcracker_${NUTCRACKER_PORT}"
    {{ bin_dir }}/nutcracker -c {{ conf_file }} -o {{ logfile }} -d -B ${SENTINEL_BNS} -S ${SENTINEL_PORT} -s  ${STATUS_PORT} -v 4 -m 16384 -w {{ whitelist_file_dir }}/whitelist -p {{ pidfile }}
    sleep 1
    if [ -f {{ pidfile }} ];then
            echo "${time} started successfully."
    else
            echo "${time} failed to start."
    fi

}

function stop(){
    echo "${time} stoping..nutcracker_${NUTCRACKER_PORT}"
    if [[ -e ./var/nutcracker.pid ]] && nutcracker_pid=$(cat ./var/nutcracker.pid) && [[ ${nutcracker_pid} != "" ]]; then
        kill -2 ${nutcracker_pid}
        sleep 2
        flag=$(ps -ef |grep -v "grep" | grep nutcracker_${NUTCRACKER_PORT} |grep ${STATUS_PORT}|wc -l)
        if [[ ${flag}==0 ]]; then
            echo "${time} stopped successfully."
        else
            echo "${time} failed to stop."
            exit 1
        fi
    else
        nutcracker_pid=$( ps -ef |grep -v "grep" | grep nutcracker_${NUTCRACKER_PORT} |grep ${STATUS_PORT}| awk '{print $2}')
        if [[ ${nutcracker_pid} == "" ]]; then
            echo "${time} nutcracker_${NUTCRACKER_PORT} does not exist!"
            exit 1
        else
            kill -2 ${nutcracker_pid} || （echo "${time} Failed to kill ${nutcracker_pid}" && exit 1）
            sleep 2
            flag=$(ps -ef |grep -v "grep" | grep nutcracker_${NUTCRACKER_PORT} |grep ${STATUS_PORT}|wc -l)
            if [[ ${flag}==0 ]]; then
                echo "${time} stopped successfully."
            else
                echo "${time} failed to stop."
                exit 1
            fi

        fi

    fi

}

case "$1" in
    status)
     # nc -zv -w 3 127.0.0.1 ${NUTCRACKER_PORT}
     netstat -nltp|grep ${NUTCRACKER_PORT}
      ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        start
        ;;

    *)
        echo "Usage: $0 {status|start|stop|restart}"
        ;;
esac
