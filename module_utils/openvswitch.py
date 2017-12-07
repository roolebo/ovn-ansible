# Copyright (c), Red Hat, Inc., 2016
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

import time
import traceback
import six

from ansible.module_utils.basic import AnsibleModule

try:
    import ovs
    import ovs.dirs
    from ovs.poller import Poller
    from ovs.db.idl import Idl, SchemaHelper, Transaction
    HAS_OVS = True
except ImportError:
    HAS_OVS = False


NB_CTL       = 'ovnnb_db.sock'
NB_DB        = 'OVN_Northbound'
NB_SCHEMA    = 'ovn-nb.ovsschema'

SB_CTL       = 'ovnsb_db.sock'
SB_DB        = 'OVN_Southbound'
SB_SCHEMA    = 'ovn-sb.ovsschema'

OVS_CTL      = 'db.sock'
OVS_DB       = 'Open_vSwitch'
OVS_SCHEMA   = 'vswitch.ovsschema'

LOGICAL_SWITCH      = 'Logical_Switch'
LOGICAL_SWITCH_PORT = 'Logical_Switch_Port'
OPEN_VSWITCH        = 'Open_vSwitch'
SB_GLOBAL           = 'SB_Global'
CONNECTION          = 'Connection'


def wait_for_db_change(idl):
    seq = idl.change_seqno
    stop = time.time() + 10
    while idl.change_seqno == seq and not idl.run():
        poller = Poller()
        idl.wait(poller)
        poller.block()
        if time.time() >= stop:
            raise Exception('Could not sync with {}'.format(idl._db.name))

def find_row(idl, table, predicate):
    for row in six.itervalues(idl.tables[table].rows):
        if predicate(row):
            return row


default_ops = {
    'register_interest': lambda schema: None,
    'prepare': lambda module, idl: None,
    'build_txn': lambda module, idl, txn: None,
    'txn_failure_msg': lambda module: 'OVSDB transaction failed',
}

def make_module(
    states=[],
    argument_spec={},
    supports_check_mode=False,
    schema_file=None,
    ctl=None,
    ops={},
):
    ops_with_defaults = {}
    for state in states:
        ops_with_defaults[state] = default_ops.copy()
        ops_with_defaults[state].update(ops.get(state, {}))

    argument_spec['state'].update({
        'choices': states,
        'type': 'str',
    })

    def ovs_run_module():
        module = AnsibleModule(
            argument_spec=argument_spec,
            supports_check_mode=supports_check_mode,
        )
        module._ovs_vars = {}

        state = module.params['state']
        op = ops_with_defaults[state]

        if not HAS_OVS:
            module.fail_json(msg='Python Open vSwitch library is not installed')

        try:
            schema_path = '{}/{}'.format(ovs.dirs.PKGDATADIR, schema_file)
            remote = 'unix:{}/{}'.format(ovs.dirs.RUNDIR, ctl)
            schema = SchemaHelper(location=schema_path)
            op['register_interest'](schema)
            idl = Idl(remote, schema)

            try:
                wait_for_db_change(idl)
            except Exception as e:
                module.fail_json(msg=str(e), exception=traceback.format_exc())

            op['prepare'](module, idl)

            if not module.check_mode:
                for i in range(3):
                    txn = Transaction(idl)
                    op['build_txn'](module, idl, txn)
                    status = txn.commit_block()
                    if status == Transaction.SUCCESS:
                        break
                    elif status != Transaction.TRY_AGAIN:
                        break

                if status == Transaction.SUCCESS:
                    changed = True
                elif status == Transaction.UNCHANGED:
                    changed = False
                else:
                    msg = op['txn_failure_msg'](module)
                    module.fail_json(msg='{}: {}'.format(msg, status))
            else:
                changed = True

            module.exit_json(changed=changed)
        except Exception as e:
            module.fail_json(msg=str(e), exception=traceback.format_exc())
        finally:
            if 'idl' in locals():
                idl.close()

    return ovs_run_module

