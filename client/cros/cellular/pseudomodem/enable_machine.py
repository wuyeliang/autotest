# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mm1
import state_machine

class EnableMachine(state_machine.StateMachine):
    def Cancel(self):
        logging.info('EnableMachine: Canceling enable.')
        super(EnableMachine, self).Cancel()
        state = self._modem.Get(mm1.I_MODEM, 'State')
        reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
        if state == mm1.MM_MODEM_STATE_ENABLING:
            logging.info('EnableMachine: Setting state to DISABLED.')
            self._modem.ChangeState(mm1.MM_MODEM_STATE_DISABLED, reason)
        self._modem.enable_step = None

    def _HandleDisabledState(self):
        assert self._modem.disable_step is None
        assert self._modem.connect_step is None
        assert self._modem.disconnect_step is None
        logging.info('EnableMachine: Setting state to ENABLING')
        reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
        self._modem.ChangeState(mm1.MM_MODEM_STATE_ENABLING, reason)
        return True

    def _HandleEnablingState(self):
        assert self._modem.disable_step is None
        assert self._modem.connect_step is None
        assert self._modem.disconnect_step is None
        logging.info('EnableMachine: Setting state to ENABLED.')
        reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED
        self._modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED, reason)
        return True

    def _HandleEnabledState(self):
        assert self._modem.disable_step is None
        assert self._modem.connect_step is None
        assert self._modem.disconnect_step is None
        logging.info('EnableMachine: Searching for networks.')
        self._modem.enable_step = None
        self._modem.RegisterWithNetwork()
        return False

    def _GetModemStateFunctionMap(self):
        return {
            mm1.MM_MODEM_STATE_DISABLED: EnableMachine._HandleDisabledState,
            mm1.MM_MODEM_STATE_ENABLING: EnableMachine._HandleEnablingState,
            mm1.MM_MODEM_STATE_ENABLED: EnableMachine._HandleEnabledState
        }

    def _ShouldStartStateMachine(self):
        state = self._modem.Get(mm1.I_MODEM, 'State')
        if self._modem.enable_step and self._modem.enable_step != self:
            # There is already an enable operation in progress.
            logging.error('There is already an ongoing enable operation')
            if state == mm1.MM_MODEM_STATE_ENABLING:
                message = 'Modem enable already in progress.'
            else:
                message = 'Modem enable has already been initiated' \
                          ', ignoring.'
            raise mm1.MMCoreError(mm1.MMCoreError.IN_PROGRESS, message)
        elif self._modem.enable_step is None:
            # There is no enable operation going on, cancelled or otherwise.
            if state != mm1.MM_MODEM_STATE_DISABLED:
                message = 'Modem cannot be enabled if not in the DISABLED' \
                          ' state.'
                logging.error(message)
                raise mm1.MMCoreError(mm1.MMCoreError.WRONG_STATE, message)
            logging.info('Starting Enable')
            self._modem.enable_step = self
        return True
