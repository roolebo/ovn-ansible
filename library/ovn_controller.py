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
    OVS_CTL,
    OVS_SCHEMA,
    OPEN_VSWITCH,
    find_row,
    make_module,
)

fields = {
    'remote': {'type': "str"},
    'encap_type': {'type': "str"},
    'encap_ip': {'type': "str"},
    'bridge_mappings': {'type': 'dict'},
    'state': {
        "default": "present",
    },
}

required_args = {
    'remote': 'ovn-remote',
    'encap_type': 'ovn-encap-type',
    'encap_ip': 'ovn-encap-ip',
}

optional_args = {
    'bridge_mappings': 'ovn-bridge-mappings',
}

def serialize_dict(value):
    return ','.join('{}:{}'.format(k,v) for k, v in six.iteritems(value))

serializer = {
    'bridge_mappings': serialize_dict,
}

args = {}
args.update(required_args)
args.update(optional_args)


def register_interest(schema):
    schema.register_columns(OPEN_VSWITCH, ['external_ids'])


def prepare_present(module, idl):
    for arg in required_args:
        if module.params[arg] is None:
            msg = "{} is required argument for state 'present'".format(arg)
            module.fail_json(msg=msg)

    ovs_table = idl.tables.get(OPEN_VSWITCH)
    ovs_config = six.next(six.itervalues(ovs_table.rows))
    for arg in args:
        if module.params[arg] is not None:
            if arg in serializer:
                serialized = serializer[arg](module.params[arg])
            else:
                serialized = module.params[arg]
        else:
            serialized = None

        if serialized != ovs_config.external_ids.get(args[arg], None):
            break
    else:
        module.exit_json(changed=False)


def prepare_absent(module, idl):
    ovs_table = idl.tables.get(OPEN_VSWITCH)
    ovs_config = six.next(six.itervalues(ovs_table.rows))
    for arg in args:
        if ovs_config.external_ids.get(args[arg]) is not None:
            break
    else:
        module.exit_json(changed=False)


def setup_ovn_controller(module, idl, txn):
    ovs_table = idl.tables.get(OPEN_VSWITCH)
    ovs_config = six.next(six.itervalues(ovs_table.rows))
    for arg in args:
        if module.params[arg] is not None:
            if arg in serializer:
                serialized = serializer[arg](module.params[arg])
            else:
                serialized = module.params[arg]
            ovs_config.setkey('external_ids', args[arg], serialized)
        else:
            ovs_config.delkey('external_ids', args[arg])


def remove_ovn_controller(module, idl, txn):
    ovs_table = idl.tables.get(OPEN_VSWITCH)
    ovs_config = six.next(six.itervalues(ovs_table.rows))
    for arg in args:
        if args[arg] in ovs_config.external_ids:
            ovs_config.delkey('external_ids', args[arg])


def setup_failure_msg(module):
    return 'Failed to setup OVN controller'


def remove_failure_msg(module):
    return 'Failed to remove OVN controller'


run_module = make_module(
    argument_spec=fields,
    states=['present', 'absent'],
    supports_check_mode=True,
    schema_file=OVS_SCHEMA,
    ctl=OVS_CTL,
    ops={
        'present': {
            'register_interest': register_interest,
            'prepare': prepare_present,
            'build_txn': setup_ovn_controller,
            'txn_failure_msg': setup_failure_msg,
        },
        'absent': {
            'register_interest': register_interest,
            'prepare': prepare_absent,
            'build_txn': remove_ovn_controller,
            'txn_failure_msg': remove_failure_msg,
        },
    },
)

if __name__ == '__main__':
    run_module()
