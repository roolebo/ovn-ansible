#!/usr/bin/python

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
    'name': {"required": True, type: "str"},
    'switch': {"required": True, type: "str"},
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
        type: "str",
    },
    'addresses': {
        'default': [],
        type: 'list',
    },
    'state': {
        "default": "present",
    },
}

props = [
    'type',
    'addresses',
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
                module.log('prop {}, current: {}({}), requested: {}({})'.format(
                    prop,
                    getattr(port, prop),
                    type(getattr(port, prop)),
                    module.params[prop],
                    type(module.params[prop]),
                ))
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


def configure_port(module, idl, txn):
    switch = module._ovs_vars['switch']
    if module._ovs_vars.get('should_add'):
        table = idl.tables.get(LOGICAL_SWITCH_PORT)
        port = txn.insert(table)
        port.name = module.params['name']
        switch.addvalue('ports', port.uuid)
    else:
        port = module._ovs_vars['port']
        if module._ovs_vars.get('should_reconfigure'):
            for prop in props:
                setattr(port, prop, module.params[prop])


def remove_port(module, idl, txn):
    module._ovs_vars['switch'].delete()


def create_failure_msg(module):
    op = 'add' if module._ovs_vars['port'] is None else 'update'
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
#            'txn_failure_msg': create_failure_msg,
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
