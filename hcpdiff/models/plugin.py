"""
plugin.py
====================
    :Name:        model plugin
    :Author:      Dong Ziyi
    :Affiliation: HCP Lab, SYSU
    :Created:     10/03/2023
    :Licence:     Apache-2.0
"""

from typing import Tuple, List, Dict

import torch
from torch import nn
import weakref

class BasePluginBlock(nn.Module):

    def forward(self, fea_in:Tuple[torch.Tensor], fea_out:torch.Tensor):
        return fea_out

    def remove(self):
        pass

class SinglePluginBlock(BasePluginBlock):
    def __init__(self, layer:nn.Module):
        super().__init__()
        self.host = weakref.ref(layer)

        self.hook_handle = layer.register_forward_hook(self.layer_hook)

    def layer_hook(self, host, fea_in:Tuple[torch.Tensor], fea_out:torch.Tensor):
        return self(fea_in, fea_out)

    def remove(self):
        self.hook_handle.remove()

class PluginBlock(BasePluginBlock):
    def __init__(self, from_layer:nn.Module, to_layer:nn.Module, pre_hook_to=False):
        super().__init__()
        self.host_from = weakref.ref(from_layer)
        self.host_to = weakref.ref(to_layer)
        #self.pre_hook_to = pre_hook_to

        self.hook_handle_from = from_layer.register_forward_hook(self.from_layer_hook)
        if pre_hook_to:
            self.hook_handle_to = to_layer.register_forward_pre_hook(self.to_layer_pre_hook)
        else:
            self.hook_handle_to = to_layer.register_forward_hook(self.to_layer_hook)

    def from_layer_hook(self, host, fea_in:Tuple[torch.Tensor], fea_out:torch.Tensor):
        self.feat_from = fea_out

    def to_layer_hook(self, host, fea_in:Tuple[torch.Tensor], fea_out:torch.Tensor):
        return self(self.feat_from, fea_out)

    def to_layer_pre_hook(self, host, fea_in:torch.Tensor):
        return self(self.feat_from, fea_in)

    def remove(self):
        self.hook_handle_from.remove()
        self.hook_handle_to.remove()

class MultiPluginBlock(BasePluginBlock):
    def __init__(self, from_layers:List[nn.Module], to_layers:List[nn.Module], pre_hook_to=False):
        super().__init__()
        self.host_from = [weakref.ref(x) for x in from_layers]
        self.host_to = [weakref.ref(x) for x in to_layers]

        self.feat_from=[None for _ in range(len(from_layers))]

        self.hook_handle_from = []
        self.hook_handle_to = []

        for idx, layer in enumerate(from_layers):
            handle_from = layer.register_forward_hook(lambda host, fea_in, fea_out:self.from_layer_hook(host, fea_in, fea_out, idx))
            self.hook_handle_from.append(handle_from)
        for idx, layer in enumerate(to_layers):
            if pre_hook_to:
                handle_to = layer.register_forward_pre_hook(lambda host, fea_in:self.to_layer_pre_hook(host, fea_in, idx))
            else:
                handle_to = layer.register_forward_hook(lambda host, fea_in, fea_out:self.to_layer_hook(host, fea_in, fea_out, idx))
            self.hook_handle_to.append(handle_to)

        self.record_count=0

    def from_layer_hook(self, host, fea_in:Tuple[torch.Tensor], fea_out:Tuple[torch.Tensor], idx: int):
        self.feat_from[idx] = fea_out
        self.record_count+=1
        if self.record_count==len(self.feat_from): # call forward when all feat is record
            self.record_count = 0
            self.feat_to = self(self.feat_from)

    def to_layer_hook(self, host, fea_in:Tuple[torch.Tensor], fea_out:Tuple[torch.Tensor], idx: int):
        return self.feat_to[idx] + fea_out

    def to_layer_pre_hook(self, host, fea_in:Tuple[torch.Tensor], idx: int):
        return self.feat_to[idx] + fea_in

    def remove(self):
        for handle_from in self.hook_handle_from:
            handle_from.remove()
        for handle_to in self.hook_handle_to:
            handle_to.remove()

class PluginGroup:
    def __init__(self, plugin_dict:Dict[str, BasePluginBlock]):
        self.plugin_dict = plugin_dict

    def __setitem__(self, k, v):
        self.plugin_dict[k]=v

    def __getitem__(self, k):
        return self.plugin_dict[k]

    def remove(self):
        for plugin in self.plugin_dict.values():
            plugin.remove()

    def state_dict(self, model=None):
        if model is None:
            return {f'{k}.{ks}':vs for k,v in self.plugin_dict.items() for ks,vs in v.state_dict().items()}
        else:
            sd_model = model.state_dict()
            return {f'{k}.{ks}':sd_model[f'{k}.{v.id}.{ks}'] for k,v in self.plugin_dict.items() for ks,vs in v.state_dict().items()}

    def empty(self):
        return len(self.plugin_dict)==0

