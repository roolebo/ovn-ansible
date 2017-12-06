#!/usr/bin/python

import traceback

from ansible.module_utils.openvswitch import (
    NB_CTL,
    NB_SCHEMA,
    LOGICAL_SWITCH,
    find_row,
    make_module,
)

fields = {
    'name': {"required": True, type: "str"},
    'state': {
        "default": "present",
    },
}

def register_interest(schema):
    schema.register_columns(LOGICAL_SWITCH, ['name'])


def switch_exists(module, idl, exit_if_present):
    has_requested_switch = lambda row: row.name == module.params['name']
    row = find_row(idl, LOGICAL_SWITCH, has_requested_switch)
    if row:
        module._ovs_vars['switch'] = row
    if not (bool(row) ^ exit_if_present):
        module.exit_json(changed=False)


def prepare_present(module, idl):
    switch_exists(module, idl, exit_if_present=True)


def prepare_absent(module, idl):
    switch_exists(module, idl, exit_if_present=False)


def add_switch(module, idl, txn):
    table = idl.tables.get(LOGICAL_SWITCH)
    switch = txn.insert(table)
    switch.name = module.params['name']


def remove_switch(module, idl, txn):
    module._ovs_vars['switch'].delete()


def create_failure_msg(module):
    return 'Failed to create logical switch {}'.format(module.params['name'])


def remove_failure_msg(module):
    return 'Failed to delete logical switch {}({})'.format(
        module.params['name'],
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
            'build_txn': add_switch,
            'txn_failure_msg': create_failure_msg,
        },
        'absent': {
            'register_interest': register_interest,
            'prepare': prepare_absent,
            'build_txn': remove_switch,
            'txn_failure_msg': remove_failure_msg,
        },
    },
)

if __name__ == '__main__':
    run_module()
