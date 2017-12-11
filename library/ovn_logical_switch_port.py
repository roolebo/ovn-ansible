#!/usr/bin/python
#
# Copyright (c), Roman Bolshakov <roolebo@gmail.com>, 2017
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.

import traceback

from ansible.module_utils.openvswitch import (
    NB_CTL,
    NB_SCHEMA,
    LOGICAL_SWITCH,
    LOGICAL_SWITCH_PORT,
    find_row,
    make_module,
)

fields = {
    'name': {"required": True, 'type': "str"},
    'switch': {"required": True, 'type': "str"},
    'type': {
        "choices": [
            '',
            'router',
            'localnet',
            'localport',
            'l2gateway',
            'vtep',
        ],
        'default': '',
        'type': "str",
    },
    'addresses': {
        'default': [],
        'type': 'list',
    },
    'options': {
        'default': {},
        'type': 'dict',
    },
    'state': {
        "default": "present",
    },
}

props = [
    'type',
    'addresses',
    'options',
]

def register_interest(schema):
    schema.register_columns(LOGICAL_SWITCH, ['name', 'ports'])
    schema.register_table(LOGICAL_SWITCH_PORT)


def prepare_present(module, idl):
    switch_name = module.params['switch']
    port_name = module.params['name']
    has_requested_switch = lambda row: row.name == switch_name
    switch = find_row(idl, LOGICAL_SWITCH, has_requested_switch)
    if switch:
        module._ovs_vars['switch'] = switch
    else:
        msg = 'Switch {} does not exist'.format(switch_name)
        module.fail_json(msg=msg)

    has_requested_port = lambda row: row.name == port_name

    port = find_row(idl, LOGICAL_SWITCH_PORT, has_requested_port)

    if port:
        module._ovs_vars['port'] = port
        if port in switch.ports:
            for prop in props:
                if getattr(port, prop) != module.params[prop]:
                    break
            else:
                module.exit_json(changed=False)
            module._ovs_vars['should_reconfigure'] = True
        else:
            # TODO support resassignment of ports from switch to switch
            module.fail_json(msg="Can't reassing port {}".format(port.name))
    else:
        module._ovs_vars['should_add'] = True


def prepare_absent(module, idl):
    port_exists(module, idl, exit_if_present=False)


def set_props_from_args(entity, props, module):
    for prop in props:
        setattr(entity, prop, module.params[prop])


def configure_port(module, idl, txn):
    switch = module._ovs_vars['switch']
    if module._ovs_vars.get('should_add'):
        table = idl.tables.get(LOGICAL_SWITCH_PORT)
        port = txn.insert(table)
        port.name = module.params['name']
        switch.addvalue('ports', port.uuid)
        set_props_from_args(port, props, module)
    else:
        port = module._ovs_vars['port']
        if module._ovs_vars.get('should_reconfigure'):
            set_props_from_args(port, props, module)


def remove_port(module, idl, txn):
    module._ovs_vars['switch'].delete()


def create_failure_msg(module):
    op = 'add' if module._ovs_vars.get('should_add') else 'update'
    return 'Failed to {} port {}'.format(op, module.params['name'])


def remove_failure_msg(module):
    return 'Failed to delete port {}({}) from {}({})'.format(
        module.params['name'],
        module._ovs_vars['port'].uuid,
        module.params['switch'],
        module._ovs_vars['switch'].uuid,
    )


run_module = make_module(
    argument_spec=fields,
    states=['present', 'absent'],
    supports_check_mode=True,
    schema_file=NB_SCHEMA,
    ctl=NB_CTL,
    ops={
        'present': {
            'register_interest': register_interest,
            'prepare': prepare_present,
            'build_txn': configure_port,
            'txn_failure_msg': create_failure_msg,
        },
        'absent': {
            'register_interest': register_interest,
#            'prepare': prepare_absent,
#            'build_txn': remove_switch,
#            'txn_failure_msg': remove_failure_msg,
        },
    },
)

if __name__ == '__main__':
    run_module()
