# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side audio test using the Chameleon board."""

import logging
import os
import time
import threading

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import chameleon_audio_helper
from autotest_lib.server.cros.audio import audio_test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class audio_AudioAfterSuspend(audio_test.AudioTest):
    """Server side audio test.

    This test talks to a Chameleon board and a Cros device to verify
    audio function of the Cros device.

    """
    version = 1
    DELAY_BEFORE_RECORD_SECONDS = 0.5
    RECORD_SECONDS = 5
    RESUME_TIMEOUT_SECS = 60
    SHORT_WAIT = 2
    SUSPEND_SECONDS = 30

    PLUG_CONFIGS = [
        # (plugged_before_suspend, plugged_after_suspend, plugged_before_resume)
        (True, True, True),
        (True, False, False),
        (True, False, True),
        (False, True, True),
        (False, True, False),
        ]

    def action_plug_jack(self, plug_state):
        """Calls the audio interface API and plugs/unplugs.

        @param plug_state: plug state to switch to

        """
        logging.debug('Plugging' if plug_state else 'Unplugging')
        jack_plugger = self.audio_board.get_jack_plugger()
        if plug_state:
            jack_plugger.plug()
        else:
            jack_plugger.unplug()
        time.sleep(self.SHORT_WAIT)


    def action_suspend(self, suspend_time=SUSPEND_SECONDS):
        """Calls the host method suspend.

        @param suspend_time: time to suspend the device for.

        """
        self.host.suspend(suspend_time=suspend_time)


    def suspend_resume(self, plugged_before_suspend, plugged_after_suspend,
                                plugged_before_resume):
        """Performs the mix of suspend/resume and plug/unplug

        @param plugged_before_suspend: plug state before suspend
        @param plugged_after_suspend: plug state after suspend
        @param plugged_before_resume: plug state before resume

        """
        plugged_after_resume = True
        # Reverse plugged states, when internal audio is tested
        if self.is_internal:
            plugged_after_resume = False
            plugged_before_suspend = not plugged_before_suspend
            plugged_after_suspend = not plugged_after_suspend
            plugged_before_resume = not plugged_before_resume


        logging.info('TEST CASE: %s > suspend > %s > %s > resume > %s',
                        'plug' if plugged_before_suspend else 'unplug',
                        'plug' if plugged_after_suspend else 'unplug',
                        'plug' if plugged_before_resume else 'unplug',
                        'plug' if plugged_after_resume else 'unplug')
        # Plugged before suspended
        self.action_plug_jack(plugged_before_suspend)

        # Suspend
        boot_id = self.host.get_boot_id()
        thread = threading.Thread(target=self.action_suspend)
        thread.start()
        self.host.test_wait_for_sleep(self.SUSPEND_SECONDS / 3)

        # Plugged after suspended
        self.action_plug_jack(plugged_after_suspend)

        # Plugged before resumed
        self.action_plug_jack(plugged_before_resume)

        self.host.test_wait_for_resume(boot_id, self.RESUME_TIMEOUT_SECS)

        # Active (plugged for external) state after resume
        self.action_plug_jack(plugged_after_resume)


    def check_correct_audio_node_selected(self):
        """Checks the node selected by Cras is correct."""
        audio_facade = self.factory.create_audio_facade()
        audio_test_utils.check_audio_nodes(audio_facade, self.audio_nodes)


    def play_and_record(self, source_widget, recorder_widget):
        """Plays and records audio

        @param source_widget: widget to do the playback
        @param recorder_widget: widget to do the recording

        """
        self.check_correct_audio_node_selected()

        # Play, wait for some time, and then start recording.
        # This is to avoid artifact caused by codec initialization.
        source_widget.set_playback_data(self.golden_file)
        logging.debug('Start playing %s', self.golden_file.path)
        source_widget.start_playback()

        time.sleep(self.DELAY_BEFORE_RECORD_SECONDS)
        logging.debug('Start recording.')
        recorder_widget.start_recording()

        time.sleep(self.RECORD_SECONDS)

        recorder_widget.stop_recording()
        logging.debug('Stopped recording.')
        recorder_widget.read_recorded_binary()


    def save_and_check_data(self, recorder_widget):
        """Saves and checks the data from the recorder

        @param recorder_widget: recorder widget to save data from

        @raise error.TestFail: if comparison fails

        """
        recorded_file = os.path.join(self.resultsdir, "recorded.raw")
        logging.debug('Saving recorded data to %s', recorded_file)
        recorder_widget.save_file(recorded_file)

        # Removes the beginning of recorded data. This is to avoid artifact
        # caused by codec initialization in the beginning of
        # recording.
        recorder_widget.remove_head(2.0)

        # Removes noise by a lowpass filter.
        recorder_widget.lowpass_filter(self.low_pass_freq)
        recorded_file = os.path.join(self.resultsdir,
                                        "recorded_filtered.raw")
        logging.debug('Saving filtered data to %s', recorded_file)
        recorder_widget.save_file(recorded_file)


        # Compares data by frequency.
        if not chameleon_audio_helper.compare_recorded_result(
                self.golden_file, recorder_widget, 'frequency'):
            raise error.TestFail('Recorded and playback file do not match')


    def run_once(self, host, audio_nodes, golden_data,
                 bind_from=None, bind_to=None,
                 source=None, recorder=None, is_internal=False):
        """Runs the test main workflow

        @param host: A host object representing the DUT.
        @param audio_nodes: audio nodes supposed to be selected.
        @param golden_data: audio file and low pass filter frequency
           the audio file should be test data defined in audio_test_data
        @param bind_from: audio originating entity to be binded
            should be defined in chameleon_audio_ids
        @param bind_to: audio directed_to entity to be binded
            should be defined in chameleon_audio_ids
        @param source: source widget entity
            should be defined in chameleon_audio_ids
        @param recorder: recorder widget entity
            should be defined in chameleon_audio_ids
        @param is_internal: whether internal audio is tested flag

        """

        self.host = host
        self.audio_nodes = audio_nodes
        self.is_internal=is_internal
        self.golden_file, self.low_pass_freq = golden_data
        chameleon_board = self.host.chameleon
        factory = remote_facade_factory.RemoteFacadeFactory(self.host)
        chameleon_board.reset()
        widget_factory = chameleon_audio_helper.AudioWidgetFactory(
                factory, host)

        # Two widgets are binded in the factory if necessary
        binder_widget = None
        bind_from_widget = None
        bind_to_widget = None
        if bind_from != None and bind_to != None:
            bind_from_widget = widget_factory.create_widget(bind_from)
            bind_to_widget = widget_factory.create_widget(bind_to)
            binder_widget = widget_factory.create_binder(bind_from_widget,
                                                         bind_to_widget)

        # Additional widgets that could be part of the factory
        if source == None:
            source_widget = bind_from_widget
        else:
            source_widget = widget_factory.create_widget(source)
        if recorder == None:
            recorder_widget = bind_to_widget
        else:
            recorder_widget = widget_factory.create_widget(recorder)

        self.audio_board = chameleon_board.get_audio_board()

        # If there is no audio-board, test default state.
        if self.audio_board == None:
            plug_configs = [(True,True,True)]
        else:
            plug_configs = self.PLUG_CONFIGS

        for (plugged_before_suspend, plugged_after_suspend,
                 plugged_before_resume) in plug_configs:
            self.suspend_resume(plugged_before_suspend,
                                plugged_after_suspend,
                                plugged_before_resume)
            if binder_widget != None:
                with chameleon_audio_helper.bind_widgets(binder_widget):
                    self.play_and_record(source_widget, recorder_widget)
            else:
                self.play_and_record(source_widget, recorder_widget)

            self.save_and_check_data(recorder_widget)
