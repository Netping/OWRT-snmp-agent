#!/usr/bin/env python3

import os
import sys
import re
import importlib
from journal import journal
from subprocess import run, CalledProcessError

try:
    import ubus
except ImportError:
    journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "Failed import ubus.")
    sys.exit(-1)

snmpd_agent = "/etc/config/snmpd"
exec_file = "owrt-snmp-pass-agent.py"
abspath = os.path.abspath(__file__)
dir_abspath = os.path.dirname(abspath)
pass_exec = f"{dir_abspath}/{exec_file}"
module_netping = 'netping'

def exit_prog(ret_val):
    ubus.disconnect()
    sys.exit(ret_val)


def create_list_node():
    search_folder = "/etc/netping/"
    dir_snmp_oid = "/snmp_oid/"
    suffix_snmp_oid = "_oid"
    snmp_pass = []

    for owrt_module in os.listdir(search_folder):
        if os.path.isdir(search_folder + owrt_module):
            name_module = re.sub("[^A-Za-z0-9]", "", owrt_module).lower()
            absolut_dir_snmp_oid = search_folder + owrt_module + dir_snmp_oid
            if os.path.isfile(absolut_dir_snmp_oid + name_module + suffix_snmp_oid + ".py"):
                sys.path.insert(1, absolut_dir_snmp_oid)
                imp_mod = importlib.import_module(name_module + suffix_snmp_oid)
                get_define_class = getattr(imp_mod, name_module)
                tmp_config = get_define_class()
                for node in tmp_config.resources:
                    oid = node['oid']
                    snmp_pass.append(oid)
    return snmp_pass


def create_list_pass_snmpd():
    global module_netping

    list_pass_snmpd = []
    try:
        confvalues = ubus.call("uci", "get", {"config": "snmpd"})
    except RuntimeError:
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err",
                         "create_list_pass_snmpd() error get " + snmpd_agent)
        exit_prog(-1)

    for confdict in list(confvalues[0]['values'].values()):
        if confdict['.type'] == "pass":
            try:
                if confdict['module'] == module_netping:
                    try:
                        pass_persist = confdict['persist']
                    except KeyError:
                        list_pass_snmpd.append(confdict.copy())
            except KeyError:
                continue

    return list_pass_snmpd


def node_to_snmpd(oid):
    global pass_exec

    try:
        run(['uci', 'add', 'snmpd', 'pass'],
            capture_output=True, check=True, encoding='utf-8')
    except CalledProcessError as e:
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR add section " + e.stderr)
        exit_prog(-1)

    str_param = "snmpd.@pass[-1].module=" + module_netping
    try:
        run(['uci', 'set', str_param],
            capture_output=True, check=True, encoding='utf-8')
    except CalledProcessError as e:
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR add option " + e.stderr)
        exit_prog(-1)

    str_param = "snmpd.@pass[-1].miboid=" + oid
    try:
        run(['uci', 'set', str_param],
            capture_output=True, check=True, encoding='utf-8')
    except CalledProcessError as e:
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR add option " + e.stderr)
        exit_prog(-1)

    str_param = "snmpd.@pass[-1].prog=" + pass_exec
    try:
        run(['uci', 'set', str_param],
            capture_output=True, check=True, encoding='utf-8')
    except CalledProcessError as e:
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR add option " + e.stderr)
        exit_prog(-1)

    try:
        run(['uci', 'commit', 'snmpd'])
    except CalledProcessError as e:
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR commit snmpd " + e.stderr)
        exit_prog(-1)

    run(['/etc/init.d/snmpd', 'restart'])


def update_snmpd_pass(netping_pass_oid, snmpd_pass_name):
    ubus.call("uci", "delete", {"config": "snmpd", "section": snmpd_pass_name})
    ubus.call("uci", "commit", {"config": "snmpd"})
    node_to_snmpd(netping_pass_oid)


def check_add_pass(netping_pass_oid, list_pass_snmpd):
    for pass_snmpd in list_pass_snmpd:
        try:
            if netping_pass_oid == pass_snmpd['miboid']:
                break
        except KeyError:
            continue
    else:
        # add pass oid to snmpd
        node_to_snmpd(netping_pass_oid)


def check_edit_pass(netping_pass_oid, list_pass_snmpd):
    global module_netping
    global pass_exec

    for pass_snmpd in list_pass_snmpd:
        try:
            if netping_pass_oid == pass_snmpd['miboid'] and pass_snmpd['module'] == module_netping:
                try:
                    if pass_snmpd['prog'] != pass_exec:
                        update_snmpd_pass(netping_pass_oid, pass_snmpd['.name'])
                except KeyError:
                    update_snmpd_pass(netping_pass_oid, pass_snmpd['.name'])
                finally:
                    break
        except KeyError:
            continue


def check_del_pass(pass_snmpd, list_pass_oids):
    for pass_oids in list_pass_oids:
        if pass_oids == pass_snmpd['miboid']:
            break
    else:
        ubus.call("uci", "delete", {"config": "snmpd", "section": pass_snmpd['.name']})
        ubus.call("uci", "commit", {"config": "snmpd"})


def change_config_snmpd(list_pass_oids):
    global pass_exec

    list_pass_snmpd = create_list_pass_snmpd()
    for netping_pass_oid in list_pass_oids:
        check_add_pass(netping_pass_oid, list_pass_snmpd)
        check_edit_pass(netping_pass_oid, list_pass_snmpd)

    for pass_snmpd in list_pass_snmpd:
        check_del_pass(pass_snmpd, list_pass_oids)


if __name__ == '__main__':
    journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", "Start module!")

    if not os.path.exists(snmpd_agent):
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR snmpd agent not installed")
        journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", "Failed finish module")
        sys.exit(-1)

    if not ubus.connect("/var/run/ubus.sock"):
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "Failed connect to ubus")
        journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", "Failed finish module")
        sys.exit(-1)

    list_pass_oids = create_list_node()
    change_config_snmpd(list_pass_oids)

    journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", "Success finish module")
    exit_prog(0)
