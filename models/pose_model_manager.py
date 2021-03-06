#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: Donny You(youansheng@gmail.com)
# Select Pose Model for pose detection.


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from models.pose.multi.capsule_net import CapsuleNet
from models.pose.multi.mobile_pose import MobilePose
from models.pose.multi.open_pose_org import get_open_pose_org
from models.pose.multi.rpn_pose import RPNPose
from models.pose.multi.open_pose import OpenPose
from models.pose.multi.capsule_pose import CapsulePose
from models.pose.single.cpm_net import CPMNet
from utils.tools.logger import Logger as Log


MULTI_POSE_MODEL_DICT = {
    'open_pose': OpenPose,
    'open_pose_org': get_open_pose_org,
    'rpn_pose': RPNPose,
    'mobile_pose': MobilePose,
    'capsule_pose': CapsulePose,
}

SINGLE_POSE_MODEL_DICT = {
    'cpm_net': CPMNet
}


class PoseModelManager(object):
    def __init__(self, configer):
        self.configer = configer

    def multi_pose_detector(self):
        model_name = self.configer.get('network', 'model_name')

        if model_name not in MULTI_POSE_MODEL_DICT:
            Log.error('Model: {} not valid!'.format(model_name))
            exit(1)

        model = MULTI_POSE_MODEL_DICT[model_name](self.configer)

        return model

    def single_pose_detector(self):
        model_name = self.configer.get('network', 'model_name')

        if model_name not in SINGLE_POSE_MODEL_DICT:
            Log.error('Model: {} not valid!'.format(model_name))
            exit(1)

        model = SINGLE_POSE_MODEL_DICT[model_name](self.configer)

        return model

    def human_filter(self):
        return CapsuleNet()