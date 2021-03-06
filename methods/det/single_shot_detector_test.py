#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: Donny You (youansheng@gmail.com)
# Class Definition for Single Shot Detector.


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from datasets.det_data_loader import DetDataLoader
from datasets.tools.transforms import Normalize, ToTensor, DeNormalize
from methods.tools.module_utilizer import ModuleUtilizer
from models.det_model_manager import DetModelManager
from utils.helpers.image_helper import ImageHelper
from utils.helpers.file_helper import FileHelper
from utils.helpers.json_helper import JsonHelper
from utils.layers.det.priorbox_layer import PriorBoxLayer
from utils.tools.logger import Logger as Log
from vis.parser.det_parser import DetParser
from vis.visualizer.det_visualizer import DetVisualizer


class SingleShotDetectorTest(object):
    def __init__(self, configer):
        self.configer = configer

        self.det_visualizer = DetVisualizer(configer)
        self.det_parser = DetParser(configer)
        self.det_model_manager = DetModelManager(configer)
        self.det_data_loader = DetDataLoader(configer)
        self.module_utilizer = ModuleUtilizer(configer)
        self.default_boxes = PriorBoxLayer(configer)()
        self.device = torch.device('cpu' if self.configer.get('gpu') is None else 'cuda')
        self.det_net = None

    def init_model(self):
        self.det_net = self.det_model_manager.object_detector()
        self.det_net = self.module_utilizer.load_net(self.det_net)
        self.det_net.eval()

    def __test_img(self, image_path, json_path, raw_path, vis_path):
        Log.info('Image Path: {}'.format(image_path))
        ori_img_rgb = ImageHelper.img2np(ImageHelper.pil_open_rgb(image_path))
        ori_img_bgr = ImageHelper.rgb2bgr(ori_img_rgb)
        inputs = ImageHelper.resize(ori_img_rgb, tuple(self.configer.get('data', 'input_size')), Image.CUBIC)
        inputs = ToTensor()(inputs)
        inputs = Normalize(mean=self.configer.get('trans_params', 'mean'),
                           std=self.configer.get('trans_params', 'std'))(inputs)

        with torch.no_grad():
            inputs = inputs.unsqueeze(0).to(self.device)
            bbox, cls = self.det_net(inputs)

        bbox = bbox.cpu().data.squeeze(0)
        cls = F.softmax(cls.cpu().squeeze(0), dim=-1).data
        boxes, lbls, scores = self.__decode(bbox, cls)
        json_dict = self.__get_info_tree(boxes, lbls, scores, ori_img_rgb)

        image_canvas = self.det_parser.draw_bboxes(ori_img_bgr.copy(),
                                                   json_dict,
                                                   conf_threshold=self.configer.get('vis', 'conf_threshold'))
        cv2.imwrite(vis_path, image_canvas)
        cv2.imwrite(raw_path, ori_img_bgr)

        Log.info('Json Path: {}'.format(json_path))
        JsonHelper.save_file(json_dict, json_path)
        return json_dict

    def __nms(self, bboxes, scores, mode='union'):
        """Non maximum suppression.

        Args:
          bboxes(tensor): bounding boxes, sized [N,4].
          scores(tensor): bbox scores, sized [N,].
          threshold(float): overlap threshold.
          mode(str): 'union' or 'min'.

        Returns:
          keep(tensor): selected indices.

        Ref:
          https://github.com/rbgirshick/py-faster-rcnn/blob/master/lib/nms/py_cpu_nms.py
        """

        x1 = bboxes[:, 0]
        y1 = bboxes[:, 1]
        x2 = bboxes[:, 2]
        y2 = bboxes[:, 3]

        areas = (x2 - x1) * (y2 - y1)
        _, order = scores.sort(0, descending=True)

        keep = []
        while order.numel() > 0:
            i = order[0]
            keep.append(i)

            if order.numel() == 1:
                break

            xx1 = x1[order[1:]].clamp(min=x1[i])
            yy1 = y1[order[1:]].clamp(min=y1[i])
            xx2 = x2[order[1:]].clamp(max=x2[i])
            yy2 = y2[order[1:]].clamp(max=y2[i])

            w = (xx2-xx1).clamp(min=0)
            h = (yy2-yy1).clamp(min=0)
            inter = w*h

            if self.configer.get('nms', 'mode') == 'union':
                ovr = inter / (areas[i] + areas[order[1:]] - inter)
            elif self.configer.get('nms', 'mode') == 'min':
                ovr = inter / areas[order[1:]].clamp(max=areas[i])
            else:
                raise TypeError('Unknown nms mode: %s.' % mode)

            ids = (ovr <= self.configer.get('nms', 'overlap_threshold')).nonzero().squeeze()
            if ids.numel() == 0:
                break

            order = order[ids + 1]

        return torch.LongTensor(keep)

    def __decode(self, loc, conf):
        """Transform predicted loc/conf back to real bbox locations and class labels.

        Args:
          loc: (tensor) predicted loc, sized [8732, 4].
          conf: (tensor) predicted conf, sized [8732, 21].

        Returns:
          boxes: (tensor) bbox locations, sized [#obj, 4].
          labels: (tensor) class labels, sized [#obj,1].

        """
        variances = [0.1, 0.2]
        wh = torch.exp(loc[:, 2:] * variances[1]) * self.default_boxes[:, 2:]
        cxcy = loc[:, :2] * variances[0] * self.default_boxes[:, 2:] + self.default_boxes[:, :2]
        boxes = torch.cat([cxcy - wh / 2, cxcy + wh / 2], 1)  # [8732,4]

        max_conf, labels = conf.max(1)  # [8732,1]
        ids = labels.nonzero()
        tmp = ids.cpu().numpy()

        if tmp.__len__() > 0:
            # print('detected %d objs' % tmp.__len__())
            ids = ids.squeeze(1)  # [#boxes,]
            keep = self.__nms(boxes[ids], max_conf[ids])

            pred_bboxes = boxes[ids][keep].cpu().numpy()
            pred_bboxes = np.clip(pred_bboxes, 0, 1)
            pred_labels = labels[ids][keep].cpu().numpy()
            pred_confs = max_conf[ids][keep].cpu().numpy()

            return pred_bboxes, pred_labels, pred_confs

        else:
            Log.info('None object detected!')
            pred_bboxes = list()
            pred_labels = list()
            pred_confs = list()
            return pred_bboxes, pred_labels, pred_confs

    def __get_info_tree(self, box_list, label_list, conf, image_raw):
        height, width, _ = image_raw.shape
        json_dict = dict()
        object_list = list()
        for bbox, label, cf in zip(box_list, label_list, conf):
            if cf < self.configer.get('vis', 'conf_threshold'):
                continue

            object_dict = dict()
            xmin = bbox[0] * width
            xmax = bbox[2] * width
            ymin = bbox[1] * height
            ymax = bbox[3] * height
            object_dict['bbox'] = [xmin, ymin, xmax, ymax]
            object_dict['label'] = label - 1
            object_dict['score'] = cf

            object_list.append(object_dict)

        json_dict['objects'] = object_list
        return json_dict

    def test(self):
        base_dir = os.path.join(self.configer.get('project_dir'),
                                'val/results/det', self.configer.get('dataset'))

        test_img = self.configer.get('test_img')
        test_dir = self.configer.get('test_dir')
        if test_img is None and test_dir is None:
            Log.error('test_img & test_dir not exists.')
            exit(1)

        if test_img is not None and test_dir is not None:
            Log.error('Either test_img or test_dir.')
            exit(1)

        if test_img is not None:
            base_dir = os.path.join(base_dir, 'test_img')
            filename = test_img.rstrip().split('/')[-1]
            json_path = os.path.join(base_dir, 'json', '{}.json'.format('.'.join(filename.split('.')[:-1])))
            raw_path = os.path.join(base_dir, 'raw', filename)
            vis_path = os.path.join(base_dir, 'vis', '{}_vis.png'.format('.'.join(filename.split('.')[:-1])))
            if not os.path.exists(os.path.dirname(json_path)):
                os.makedirs(os.path.dirname(json_path))

            if not os.path.exists(os.path.dirname(raw_path)):
                os.makedirs(os.path.dirname(raw_path))

            if not os.path.exists(os.path.dirname(vis_path)):
                os.makedirs(os.path.dirname(vis_path))

            self.__test_img(test_img, json_path, raw_path, vis_path)

        else:
            base_dir = os.path.join(base_dir, 'test_dir', test_dir.rstrip('/').split('/')[-1])
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)

            for filename in FileHelper.list_dir(test_dir):
                image_path = os.path.join(test_dir, filename)
                json_path = os.path.join(base_dir, 'json', '{}.json'.format('.'.join(filename.split('.')[:-1])))
                raw_path = os.path.join(base_dir, 'raw', filename)
                vis_path = os.path.join(base_dir, 'vis', '{}_vis.png'.format('.'.join(filename.split('.')[:-1])))
                if not os.path.exists(os.path.dirname(json_path)):
                    os.makedirs(os.path.dirname(json_path))

                if not os.path.exists(os.path.dirname(raw_path)):
                    os.makedirs(os.path.dirname(raw_path))

                if not os.path.exists(os.path.dirname(vis_path)):
                    os.makedirs(os.path.dirname(vis_path))

                self.__test_img(image_path, json_path, raw_path, vis_path)

    def debug(self):
        base_dir = os.path.join(self.configer.get('project_dir'),
                                'vis/results/det', self.configer.get('dataset'), 'debug')

        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        val_data_loader = self.det_data_loader.get_valloader()

        count = 0
        for i, (inputs, bboxes, labels) in enumerate(val_data_loader):
            for j in range(inputs.size(0)):
                count = count + 1
                if count > 20:
                    exit(1)

                ori_img_rgb = DeNormalize(mean=self.configer.get('trans_params', 'mean'),
                                          std=self.configer.get('trans_params', 'std'))(inputs[j])
                ori_img_rgb = ori_img_rgb.numpy().transpose(1, 2, 0).astype(np.uint8)
                ori_img_bgr = cv2.cvtColor(ori_img_rgb, cv2.COLOR_RGB2BGR)
                eye_matrix = torch.eye(self.configer.get('data', 'num_classes'))
                labels_target = eye_matrix[labels.view(-1)].view(inputs.size(0), -1,
                                                                 self.configer.get('data', 'num_classes'))
                boxes, lbls, scores = self.__decode(bboxes[j], labels_target[j])
                json_dict = self.__get_info_tree(boxes, lbls, scores, ori_img_rgb)
                image_canvas = self.det_parser.draw_bboxes(ori_img_bgr.copy(),
                                                           json_dict,
                                                           conf_threshold=self.configer.get('vis', 'conf_threshold'))

                cv2.imwrite(os.path.join(base_dir, '{}_{}_vis.png'.format(i, j)), image_canvas)
                cv2.imshow('main', image_canvas)
                cv2.waitKey()

