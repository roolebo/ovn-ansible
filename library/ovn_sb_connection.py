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
import six

from ansible.module_utils.openvswitch import (
    SB_CTL,
    SB_SCHEMA,
    SB_GLOBAL,
    CONNECTION,
    find_row,
    make_module,
)

fields = {
    'target': {"required": True, 'type': "str"},
    'state': {
        "default": "present",
    },
}

def register_interest(schema):
    schema.register_columns(CONNECTION, ['target'])
    schema.register_columns(SB_GLOBAL, ['connections'])


def connection_exists(module, idl, exit_if_present):
    has_target = lambda row: row.target == module.params['target']
    connection = find_row(idl, CONNECTION, has_target)
    if connection:
        module._ovs_vars['connection'] = connection
    if not (bool(connection) ^ exit_if_present):
        module.exit_json(changed=False)


def prepare_present(module, idl):
    connection_exists(module, idl, exit_if_present=True)


def prepare_absent(module, idl):
    connection_exists(module, idl, exit_if_present=False)


def add_connection(module, idl, txn):
    table = idl.tables.get(CONNECTION)
    conn = txn.insert(table)
    conn.target = module.params['target']
    sb_global = idl.tables.get(SB_GLOBAL)
    sb_config = six.next(six.itervalues(sb_global.rows))
    sb_config.addvalue('connections', conn.uuid)


def remove_connection(module, idl, txn):
    conn = module._ovs_vars['connection']
    sb_global = idl.tables.get(SB_GLOBAL)
    sb_config = six.next(six.itervalues(sb_global.rows))
    sb_config.delvalue('connections', conn.uuid)
    conn.delete()


def create_failure_msg(module):
    return 'Failed to create connection {}'.format(module.params['target'])


def remove_failure_msg(module):
    return 'Failed to delete connection {}({})'.format(
        module.params['target'],
        module._ovs_vars['connection'].uuid,
    )


run_module = make_module(
    argument_spec=fields,
    states=['present', 'absent'],
    supports_check_mode=True,
    schema_file=SB_SCHEMA,
    ctl=SB_CTL,
    ops={
        'present': {
            'register_interest': register_interest,
            'prepare': prepare_present,
            'build_txn': add_connection,
            'txn_failure_msg': create_failure_msg,
        },
        'absent': {
            'register_interest': register_interest,
            'prepare': prepare_absent,
            'build_txn': remove_connection,
            'txn_failure_msg': remove_failure_msg,
        },
    },
)

if __name__ == '__main__':
    run_module()
