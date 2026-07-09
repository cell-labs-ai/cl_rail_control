##
# Nanotec Nanolib example
# Copyright (C) Nanotec GmbH & Co. KG - All Rights Reserved
#
# This product includes software developed by the
# Nanotec GmbH & Co. KG (http://www.nanotec.com/).
#
# The Nanolib interface headers and the examples source code provided are 
# licensed under the Creative Commons Attribution 4.0 Internaltional License. 
# To view a copy of this license, 
# visit https://creativecommons.org/licenses/by/4.0/ or send a letter to 
# Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
#
# The parts of the library provided in binary format are licensed under 
# the Creative Commons Attribution-NoDerivatives 4.0 International License. 
# To view a copy of this license, 
# visit http://creativecommons.org/licenses/by-nd/4.0/ or send a letter to 
# Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
#
# @file   sampler_example.py
#
# @brief  Definition of sampler example class
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

import time
from menu_utils import Context, handle_error_message
from nanotec_nanolib import Nanolib

class SamplerNotifyCallback(Nanolib.SamplerNotify):
    """Implementation class of Nanolib.SamplerNotify, handling the notify callback"""
    def __init__(self, samplerExample):
        super().__init__()
        self.is_sampler_active = True
        if(isinstance(samplerExample, SamplerExample)):
            self.samplerExample = samplerExample
        else:
            raise Exception("Invalid SamplerExample Object")
    
    def notify(self, lastError: Nanolib.ResultVoid, samplerState, sampleDatas, applicationData):
        # Be aware that notifications are executed in the context of separate threads 
        # other than thread that started the sampler.
        # 
        # Be careful when calling Nanolib functionality here, as doing so may cause this method
        # to be called recursively, potentially causing your application to deadlock.
        # 
        # For the same reason, this method should not throw exceptions.
        self.is_sampler_active = True
        self.samplerExample.process_sampled_data(sampleDatas)
        self.samplerState = samplerState
        if(
            (samplerState != Nanolib.SamplerState_Ready) and 
            (samplerState != Nanolib.SamplerState_Running)
        ):
            if (samplerState == Nanolib.SamplerState_Failed):
                print("")
                print("Sampler execution failed with error: " + lastError.getError())
            # It's now safe to destroy (this) notification object
            self.is_sampler_active = False

class SamplerExample:
    """Demonstration sampler class."""

    def __init__(self, ctx: 'Context'):
        self.sampler_interface: Nanolib.SamplerInterface = ctx.nanolib_accessor.getSamplerInterface()
        self.sampler_configuration = Nanolib.SamplerConfiguration()

        if(isinstance(ctx.active_device, Nanolib.DeviceHandle)):
            self.device_handle = ctx.active_device
        else:
            raise Exception("Invalid DeviceHandle")
        
        # list of tracked addresses
        od_index_vector = [
            Nanolib.OdIndex(0x230F, 0x00),
            Nanolib.OdIndex(0x4014, 0x03)
        ]
        od_index_vector = Nanolib.OdIndexVector(od_index_vector)
        self.ctx = ctx # the menu context
        self.tracked_addresses = od_index_vector # store
        self.address_names = ["UpTime", "Temperature"]
        self.last_iteration = 0 # last iteration counter
        self.sample_number = 0 # current sample number
        self.trigger_value = 10 # trigger value
        self.trigger_value_inactive = self.trigger_value # store inactive value
        self.trigger_value_active = self.trigger_value + 1 # store active value
        self.trigger_address = Nanolib.OdIndex(0x2400, 0x01) # store trigger address
        self.start_trigger = Nanolib.SamplerTrigger() # store smampler trigger object
        self.start_trigger.condition = Nanolib.SamplerTriggerCondition_TC_GREATER # store trigger condition
        self.start_trigger.address = self.trigger_address # store start trigger trigger address
        self.start_trigger.value = self.trigger_value # store start trigger trigger value
        self.period_milliseconds = 1000  # sample period in milliseconds
        
    def process(self):
        """Execute all defined example functions."""
        self.process_examples_without_notification()
        self.process_examples_with_notification()

    def process_examples_without_notification(self):
        """Execute all example functions without notification callback."""
        self.process_sampler_without_notification_normal()
        self.process_sampler_without_notification_repetitive()
        self.process_sampler_without_notification_continuous()

    def process_sampler_without_notification_normal(self):
        """Execute example function for normal mode without notification callback."""
        sleep_time_sec = self.period_milliseconds / 1000.0

        print("\nSampler without notification in normal mode: ")

        self.configure(Nanolib.SamplerMode_Normal)
        self.start()

        sampler_state = self.get_sampler_state()

        while sampler_state in [Nanolib.SamplerState_Ready, Nanolib.SamplerState_Running]:
            time.sleep(sleep_time_sec)
            self.process_sampled_data()
            sampler_state = self.get_sampler_state()

        # Process any remaining data
        self.process_sampled_data()

        if sampler_state == Nanolib.SamplerState_Failed:
            self.handle_sampler_failed()
        
    def process_sampler_without_notification_repetitive(self):
        """Execute example function for repetitive mode without notification callback."""
        sleep_time_sec = self.period_milliseconds / 1000.0
        wait_time_msec = 0.05

        print("\nSampler without notification in repetitive mode: ")

        self.configure(Nanolib.SamplerMode_Repetitive)
        self.start()

        sampler_state = self.get_sampler_state()

        # wait until sampler is running
        while sampler_state not in [Nanolib.SamplerState_Running, Nanolib.SamplerState_Failed]:
            time.sleep(wait_time_msec)
            sampler_state = self.get_sampler_state()

        # Start processing sampled data
        while sampler_state in [Nanolib.SamplerState_Ready, Nanolib.SamplerState_Running]:
            time.sleep(sleep_time_sec)
            self.process_sampled_data()

            if self.last_iteration >= 4:
                # Stop the sampler after 4 iterations
                self.sampler_interface.stop(self.device_handle)

            sampler_state = self.get_sampler_state()

        # Process any remaining data
        self.process_sampled_data()

        if sampler_state == Nanolib.SamplerState_Failed:
            self.handle_sampler_failed()

    def process_sampler_without_notification_continuous(self):
        """Execute example function for continuous mode without notification callback."""
        sleep_time_sec = self.period_milliseconds / 1000.0

        print("\nSampler without notification in continuous mode: ")

        self.configure(Nanolib.SamplerMode_Continuous)
        self.start()

        sampler_state = Nanolib.SamplerState_Ready
        max_cycles = 10
        cycles = 0

        while sampler_state in [Nanolib.SamplerState_Ready, Nanolib.SamplerState_Running]:
            time.sleep(sleep_time_sec)
            self.process_sampled_data()

            cycles += 1
            if cycles == max_cycles:
                # Stop the sampler after 10 cycles
                self.sampler_interface.stop(self.device_handle)

            sampler_state = self.get_sampler_state()

        # Process any remaining data
        self.process_sampled_data()

        if sampler_state == Nanolib.SamplerState_Failed:
            self.handle_sampler_failed()

    def process_examples_with_notification(self):
        """Execute all example functions with notification callback."""
        self.process_sampler_with_notification_normal()
        self.process_sampler_with_notification_repetitive()
        self.process_sampler_with_notification_continuous()

    def process_sampler_with_notification_normal(self):
        """Execute example function for normal mode with notification callback."""
        sleep_time_sec = self.period_milliseconds / 1000.0

        print("\nSampler with notification in normal mode: ")
        
        self.configure(Nanolib.SamplerMode_Normal)

        sampler_notify = SamplerNotifyCallback(self)
        self.start(sampler_notify)

        while sampler_notify.is_sampler_active:
            time.sleep(sleep_time_sec)

    def process_sampler_with_notification_repetitive(self):
        """Execute example function for repetitive mode with notification callback."""
        sleep_time_sec = self.period_milliseconds / 1000.0
        wait_time_msec = 0.05

        print("\nSampler with notification in repetitive mode: ")

        self.configure(Nanolib.SamplerMode_Repetitive)

        sampler_notify = SamplerNotifyCallback(self)
        self.start(sampler_notify)

        # Wait for the sampler to run
        sampler_state = self.get_sampler_state()
        while sampler_state not in [Nanolib.SamplerState_Running, Nanolib.SamplerState_Failed]:
            time.sleep(wait_time_msec)
            sampler_state = self.get_sampler_state()

        # Start processing sampled data
        while sampler_notify.is_sampler_active:
            time.sleep(sleep_time_sec)

            if self.last_iteration >= 4:
                # In repetitive mode, the sampler will continue to run until it is stopped or an error occurs
                self.sampler_interface.stop(self.device_handle)
                break

    def process_sampler_with_notification_continuous(self):
        """Execute example function for continuous mode with notification callback."""
        print("\nSampler with notification in continuous mode: ")
        sleep_time_sec = (self.period_milliseconds / 1000.0) * 10 

        self.configure(Nanolib.SamplerMode_Continuous)

        sampler_notify = SamplerNotifyCallback(self)
        self.start(sampler_notify)

        time.sleep(sleep_time_sec)
        # In continuous mode, the sampler will continue to run until it is stopped or an error occurs
        self.sampler_interface.stop(self.device_handle)

    def configure(self, mode):
        """Function used for sampler configuration.
        
        :param mode: The mode to use
        """
        if mode == Nanolib.SamplerMode_Continuous:
            self.sampler_configuration.durationMilliseconds = 0
        else:
            self.sampler_configuration.durationMilliseconds = 4000

        self.sampler_configuration.periodMilliseconds = 1000
        self.sampler_configuration.preTriggerNumberOfSamples = 0 # Unused currently
        self.sampler_configuration.trackedAddresses = self.tracked_addresses
        self.sampler_configuration.startTrigger = self.start_trigger
        self.sampler_configuration.usingSoftwareImplementation = (mode == Nanolib.SamplerMode_Continuous)
        self.sampler_configuration.mode = mode

        configure_result: Nanolib.ResultVoid = self.sampler_interface.configure(self.device_handle, self.sampler_configuration)
        if(configure_result.hasError()):
            raise Exception("sampler_interface.configure:" + " " + str(configure_result.getError()))

    def start(self, sampler_notify: SamplerNotifyCallback = None, application_data=0):
        """Function to start a sampler.
        
        :param sampler_notify: Notify callback (optional)
        :param application_data: not used (optional)
        """
        self.last_iteration = 0
        self.sample_number = 0
        self.header_printed = False

        # Deactivate the start trigger
        self.ctx.nanolib_accessor.writeNumber(self.device_handle, self.trigger_value_inactive, self.trigger_address, 32)

        # start the sampler
        start_result: Nanolib.ResultVoid = self.sampler_interface.start(self.device_handle, sampler_notify, application_data)
        if(start_result.hasError()):
            raise Exception("sampler_interface.start:" + " " + str(start_result.getError()))
        
        # Activate the start trigger
        self.ctx.nanolib_accessor.writeNumber(self.device_handle, self.trigger_value_active, self.trigger_address, 32)

    def get_sampler_state(self):
        """Get the state of the sampler.
        
        :return: the sampler state
        """
        sampler_state: Nanolib.ResultSamplerState = self.sampler_interface.getState(self.device_handle)

        return sampler_state.getResult()

    def get_sampler_data(self):
        """Get the sampled data from device buffer.
        
        :return: the sampled data
        """
        sampler_data: Nanolib.ResultSampleDataArray = self.sampler_interface.getData(self.device_handle)
        return sampler_data.getResult()

    def handle_sampler_failed(self, last_error_ptr=None):
        """Error handling - Outputs last error to console and menu context.
        
        :param last_error_ptr: The last occured error (optional)
        """
        if last_error_ptr:
            last_error = last_error_ptr
        else:
            assert self.get_sampler_state() == Nanolib.SamplerState_Failed
            last_error: Nanolib.ResultVoid = self.sampler_interface.getLastError(self.device_handle)

        assert last_error.hasError()
        handle_error_message(self.ctx, "Sampler execution failed with error: ", last_error.getError())
        print(f"\nSampler execution failed with error: {last_error.getError()}")

    def process_sampled_data(self, sample_datas: Nanolib.ResultSampleDataArray = None):
        """Process and display the sampled data.
        
        :param sample_datas: The sampled data
        """
        if sample_datas is None:
            sampler_data_array: Nanolib.ResultSampleDataArray = self.sampler_interface.getData(self.device_handle)
            sample_datas = sampler_data_array.getResult()
    
        if(isinstance(sample_datas, Nanolib.SampleDataVector)):
            sample_datas: list[Nanolib.SampleData] = sample_datas
        else:
            raise Exception("process_sampled_data: invalid data type for sample_datas")
        
        number_of_tracked_addresses = len(self.tracked_addresses)

        # generate header once
        if not self.header_printed:
            header_line = "------------------------------------------------------------"
            header = f"{'Iteration':<10}{'Sample':<10}"
            i = 0
            for tracked_address in self.tracked_addresses:
                address_name = f"[{self.address_names[i]}]"
                header += f"{address_name:<14}{'Time':<8}"
                i += 1

            print(header_line)
            print(header)
            print(header_line)
            self.header_printed = True

        # go through sampled data objects
        for sample_data in sample_datas:
            sampled_values = sample_data.sampledValues
            number_of_sampled_values = len(sampled_values)

            assert number_of_sampled_values % number_of_tracked_addresses == 0

            if self.last_iteration != sample_data.iterationNumber:
                self.sample_number = 0
                self.last_iteration = sample_data.iterationNumber

            # gather sampled values for tracked addresses and output in a row
            for index in range(0, number_of_sampled_values, number_of_tracked_addresses):
                line = f"{self.last_iteration:<10}{self.sample_number:<10}"

                for tracked_address_index in range(number_of_tracked_addresses):
                    sampled_value: Nanolib.SampledValue = sampled_values[index + tracked_address_index]
                    line += f"{sampled_value.value:<14}{sampled_value.collectTimeMsec:<8}"

                print(line)
                self.sample_number += 1


