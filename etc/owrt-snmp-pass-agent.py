#!/usr/bin/python3 -u

import sys
import os
import re
import importlib
from journal import journal

list_owrt_module = []


def import_owrt_oid():
    global list_owrt_module
    search_folder = "/etc/netping/"
    dir_snmp_oid = "/snmp_oid/"
    suffix_snmp_oid = "_oid"

    for owrt_module in os.listdir(search_folder):
        if os.path.isdir(search_folder + owrt_module):
            name_module = re.sub("[^A-Za-z0-9]", "", owrt_module).lower()
            absolut_dir_snmp_oid = search_folder + owrt_module + dir_snmp_oid
            if os.path.isfile(absolut_dir_snmp_oid + name_module + suffix_snmp_oid + ".py"):
                sys.path.insert(1, absolut_dir_snmp_oid)
                imp_mod = importlib.import_module(name_module + suffix_snmp_oid)
                get_define_class = getattr(imp_mod, name_module)
                tmp_config = get_define_class()
                list_owrt_module.append(tmp_config)


if __name__ == '__main__':

    import_owrt_oid()

    if len(sys.argv) == 3 and sys.argv[1] == "-g":
        # snmp get value

        oid = sys.argv[2]
        for owrt_module in list_owrt_module:
            for nodes in owrt_module.resources:
                if oid.startswith(nodes['oid']):
                    try:
                        num_node = int(oid[len(nodes['oid']):].lstrip('.'))
                    except ValueError:
                        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "get value from incorrect oid: " + oid)
                        sys.exit(-1)

                    if num_node > 0 and num_node <= owrt_module.number_nodes:
                        #call function get value
                        if nodes['rd'] is not None:
                            ret_val = nodes['rd'](num_node)
                            print(oid)
                            print(nodes['type'])
                            print(ret_val)
                            sys.exit(0)
                        else:
                            journal.WriteLog("OWRT-snmp-agent", "Normal", "err", f"Function not defined for get value from {oid}")
                            sys.exit(-1)
                    else:
                        journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", f"Node number {oid} is out of range: {1} - {owrt_module.number_nodes}")
                        sys.exit(-1)

    elif len(sys.argv) == 3 and sys.argv[1] == "-n":
        # snmp getnext value
        oid = sys.argv[2]

        for owrt_module in list_owrt_module:
            for nodes in owrt_module.resources:
                if oid.startswith(nodes['oid']):
                    if oid == nodes['oid']:
                        num_node = 1
                        oid = f"{oid}.{num_node}"
                        if nodes['rd'] is not None:
                            ret_val = nodes['rd'](num_node)
                            print(oid)
                            print(nodes['type'])
                            print(ret_val)
                            sys.exit(0)
                        else:
                            journal.WriteLog("OWRT-snmp-agent", "Normal", "err", f"Function not defined for get value from {oid}")
                            sys.exit(-1)
                    else:
                        try:
                            num_node = int(oid[len(nodes['oid']):].lstrip('.'))
                        except ValueError:
                            journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "get value from incorrect oid: " + oid)
                            sys.exit(-1)

                        num_node += 1
                        if num_node > 0 and num_node <= owrt_module.number_nodes:
                            ret_val = nodes['rd'](num_node)
                            print(f"{nodes['oid']}.{num_node}")
                            print(nodes['type'])
                            print(ret_val)
                            sys.exit(0)

    elif len(sys.argv) == 5 and sys.argv[1] == "-s":
        # snmp set value
        oid = sys.argv[2]
        s_type = sys.argv[3]
        value = sys.argv[4]
        for owrt_module in list_owrt_module:
            for nodes in owrt_module.resources:
                if oid.startswith(nodes['oid']):
                    try:
                        num_node = int(oid[len(nodes['oid']):].lstrip('.'))
                    except ValueError:
                        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "set value to incorrect oid: " + oid)
                        print("not-writable")
                        sys.exit(-1)

                    if num_node > 0 and num_node <= owrt_module.number_nodes:
                        # call function set value
                        if nodes['wr'] is not None:
                            if s_type == nodes['type']:
                                if s_type == 'integer':
                                    try:
                                        value = int(value)
                                    except ValueError:
                                        journal.WriteLog("OWRT-snmp-agent", "Normal", "err",
                                                         "set value not integer: " + value)
                                        print("wrong-type")
                                        sys.exit(-1)
                            else:
                                print("wrong-type")
                                sys.exit(-1)

                            ret_val = nodes['wr'](num_node, value)
                            if ret_val:
                                print("not-writable")
                                sys.exit(-1)
                            else:
                                sys.exit(0)
                        else:
                            journal.WriteLog("OWRT-snmp-agent", "Normal", "err", f"Function not defined for set value to {oid}")
                            print("not-writable")
                            sys.exit(-1)
                    else:
                        journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", f"Node number {oid} is out of range: {1} - {owrt_module.number_nodes}")
                        print("not-writable")
                        sys.exit(-1)
    else:
        sys.exit(0)
