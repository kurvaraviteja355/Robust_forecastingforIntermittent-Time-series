# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

# Standard library imports
from typing import Optional, Union, List, Tuple

# Third-party imports
import torch
import torch.nn as nn
from torch import Tensor

# First-party imports
from pts.modules.block.activation import Activation

class CausalConv1D(nn.Module):
    """
    1D causal temporal convolution, where the term causal means that output[t]
    does not depend on input[t+1:]. Notice that Conv1D is not implemented in
    Gluon.

    This is the basic structure used in Wavenet [ODZ+16]_ and Temporal
    Convolution Network [BKK18]_.

    The output has the same shape as the input, while we always left-pad zeros.

    Parameters
    ----------

    channels
        The dimensionality of the output space, i.e. the number of output
        channels (filters) in the convolution.

    kernel_size
        Specifies the dimensions of the convolution window.

    dilation
        Specifies the dilation rate to use for dilated convolution.

    activation
        Activation function to use.

    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int = 1,
        activation: Optional[str] = "identity",
        **kwargs,
    ):
        super(CausalConv1D, self).__init__(**kwargs)

        self.dilation = dilation
        self.kernel_size = kernel_size
        self.padding = dilation * (kernel_size - 1)
        self.conv1d = nn.Conv1d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=kernel_size,
            dilation=dilation,
            padding=self.padding,
            **kwargs,
        )
        self.activation = Activation(activation)

    # noinspection PyMethodOverriding
    def forward(self, data: Tensor) -> Tensor:
        """
        In Gluon's conv1D implementation, input has dimension NCW where N is
        batch_size, C is channel, and W is time (sequence_length).


        Parameters
        ----------
        data
            Shape (batch_size, num_features, sequence_length)

        Returns
        -------
        Tensor
            causal conv1d output. Shape (batch_size, num_features, sequence_length)
        """
        ct = self.conv1d(data)
        ct = self.activation(ct)

        if self.kernel_size > 0:
            ct = ct[:, :, :-self.padding, ...]
        return ct

class DilatedCausalGated(nn.Module):
    """
    1D convolution with Gated mechanism, see the Wavenet papers described above.

    Parameters
    ----------
    inner_channels
        The dimensionality of the intermediate space

    out_channels
        The dimensionality of the output space

    kernel_size
        Specifies the dimensions of the convolution window.

    dilation
        Specifies the dilation rate to use for dilated convolution.
    """

    def __init__(
        self,
        in_channels: int,
        inner_channels: int,
        out_channels: int,
        kernel_size: Union[int, Tuple[int], List[int]],
        dilation: Union[int, Tuple[int], List[int]],
        **kwargs,
    ) -> None:
        super(DilatedCausalGated, self).__init__(**kwargs)

        self.conv1 = CausalConv1D(
            in_channels=in_channels,
            out_channels=inner_channels,
            kernel_size=kernel_size,
            dilation=dilation,
            activation="tanh",
        )
        self.conv2 = CausalConv1D(
            in_channels=in_channels,
            out_channels=inner_channels,
            kernel_size=kernel_size,
            dilation=dilation,
            activation="sigmoid",
        )
        self.output_conv = nn.Conv1d(            
            in_channels=inner_channels, out_channels=out_channels, kernel_size=1
        )

    # noinspection PyMethodOverriding
    def forward(self, x: Tensor) -> Tensor:
        """
        Compute the 1D convolution with Gated mechanism.

        Parameters
        ----------
        x
            input features, shape (batch_size, num_features, sequence_length)

        Returns
        -------
        Tensor
            output, shape (batch_size, num_features, sequence_length)
        """
        x1 = self.conv1(x)
        x2 = self.conv2(x)
        return self.output_conv(x1 * x2)


class ResidualSequential(nn.Sequential):
    """
    Adding residual connection to each layer of the sequential blocks
    """

    def __init__(self, **kwargs):
        super(ResidualSequential, self).__init__(**kwargs)

    # noinspection PyMethodOverriding
    def forward(self, x: Tensor) -> Tensor:
        """

        Parameters
        ----------
        x
            input tensor

        Returns
        -------
        Tensor
            output of the ResidualSequential

        """
        outs = []
        for i, block in enumerate(self._children.values()):
            out = block(x)
            outs.append(out)
            if i == 0:
                x = out
            else:
                x = x + out

        return sum(outs)
