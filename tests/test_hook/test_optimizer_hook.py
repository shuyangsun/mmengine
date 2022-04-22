# Copyright (c) OpenMMLab. All rights reserved.
from unittest.mock import Mock

import torch
from torch import nn

from mmengine.hooks import OptimizerHook


class TestOptimizerHook:

    def test_after_train_iter(self):

        class Model(nn.Module):

            def __init__(self):
                super().__init__()
                self.conv1 = nn.Conv2d(
                    in_channels=1,
                    out_channels=2,
                    kernel_size=3,
                    stride=1,
                    padding=1,
                    dilation=1)
                self.conv2 = nn.Conv2d(
                    in_channels=2,
                    out_channels=2,
                    kernel_size=3,
                    stride=1,
                    padding=1,
                    dilation=1)
                self.conv3 = nn.Conv2d(
                    in_channels=1,
                    out_channels=2,
                    kernel_size=3,
                    stride=1,
                    padding=1,
                    dilation=1)

            def forward(self, x):
                x1 = self.conv1(x)
                x2 = self.conv2(x1)
                return x1, x2

        model = Model()
        x = torch.rand(1, 1, 3, 3)

        dummy_runner = Mock()
        dummy_runner.optimizer.zero_grad = Mock(return_value=None)
        dummy_runner.optimizer.step = Mock(return_value=None)
        dummy_runner.model = model
        dummy_runner.outputs = dict()

        dummy_runner.outputs['num_samples'] = 0

        class DummyLogger():

            def __init__(self):
                self.msg = ''

            def log(self, msg=None, **kwargs):
                self.msg += msg

        dummy_runner.logger = DummyLogger()
        optimizer_hook = OptimizerHook(
            dict(max_norm=2), detect_anomalous_params=True)

        dummy_runner.outputs['loss'] = model(x)[0].sum()

        dummy_runner.outputs['loss'].backward = Mock(
            wraps=dummy_runner.outputs['loss'].backward)
        optimizer_hook.detect_anomalous_parameters = Mock(
            wraps=optimizer_hook.detect_anomalous_parameters)
        optimizer_hook.clip_grads = Mock(wraps=optimizer_hook.clip_grads)

        optimizer_hook.after_train_iter(dummy_runner, 0)
        # assert the parameters of conv2 and conv3 are not in the
        # computational graph which is with x1.sum() as root.
        assert 'conv2.weight' in dummy_runner.logger.msg
        assert 'conv2.bias' in dummy_runner.logger.msg
        assert 'conv3.weight' in dummy_runner.logger.msg
        assert 'conv3.bias' in dummy_runner.logger.msg
        assert 'conv1.weight' not in dummy_runner.logger.msg
        assert 'conv1.bias' not in dummy_runner.logger.msg
        dummy_runner.optimizer.step.assert_called()
        dummy_runner.outputs['loss'].backward.assert_called()
        optimizer_hook.clip_grads.assert_called()
        optimizer_hook.detect_anomalous_parameters.assert_called()

        dummy_runner.outputs['loss'] = model(x)[1].sum()
        dummy_runner.logger.msg = ''
        optimizer_hook.after_train_iter(dummy_runner, 0)
        # assert the parameters of conv3 are not in the computational graph
        assert 'conv3.weight' in dummy_runner.logger.msg
        assert 'conv3.bias' in dummy_runner.logger.msg
        assert 'conv2.weight' not in dummy_runner.logger.msg
        assert 'conv2.bias' not in dummy_runner.logger.msg
        assert 'conv1.weight' not in dummy_runner.logger.msg
        assert 'conv1.bias' not in dummy_runner.logger.msg

        # grad_clip is None and detect_anomalous_parameters is False
        optimizer_hook = OptimizerHook(detect_anomalous_params=False)
        optimizer_hook.detect_anomalous_parameters = Mock(
            wraps=optimizer_hook.detect_anomalous_parameters)
        optimizer_hook.clip_grads = Mock(wraps=optimizer_hook.clip_grads)
        dummy_runner.outputs['loss'] = model(x)[0].sum()
        dummy_runner.outputs['loss'].backward = Mock(
            wraps=dummy_runner.outputs['loss'].backward)

        optimizer_hook.after_train_iter(dummy_runner, 0)

        dummy_runner.optimizer.step.assert_called()
        dummy_runner.outputs['loss'].backward.assert_called()
        optimizer_hook.clip_grads.assert_not_called()
        optimizer_hook.detect_anomalous_parameters.assert_not_called()