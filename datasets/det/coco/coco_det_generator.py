#!/usr/bin/env python
# -*- coding:utf-8 -*-
# Author: Donny You(youansheng@gmail.com)
# COCO det data generator.


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import os
import argparse
import shutil

from pycocotools.coco import COCO


JOSN_DIR = 'json'
IMAGE_DIR = 'image'
CAT_DICT = {
    'aeroplane': 0, 'bicycle':1,'bird':2,'boat':3,'bottle':4,
    'bus': 5, 'car': 6, 'cat': 7, 'chair': 8, 'cow': 9, 'diningtable': 10,
    'dog': 11, 'horse': 12, 'motorbike': 13, 'person': 14, 'pottedplant': 15,
    'sheep': 16, 'sofa': 17, 'train': 18, 'tvmonitor': 19
}


class CocoDetGenerator(object):

    def __init__(self, args, json_dir=JOSN_DIR, image_dir=IMAGE_DIR):
        self.args = args
        self.json_dir = os.path.join(self.args.save_dir, json_dir)
        if not os.path.exists(self.json_dir):
            os.makedirs(self.json_dir)

        self.image_dir = os.path.join(self.args.save_dir, image_dir)
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)

        self.coco = COCO(self.args.anno_file)
        self.cat_ids = self.coco.getCatIds(catNms=CAT_DICT.keys())
        self.img_ids = list(self.coco.imgs.keys())

    def generate_label(self):
        for i, img_id in enumerate(self.img_ids):
            json_dict = dict()
            ann_ids = self.coco.getAnnIds(imgIds=img_id)
            img_anns = self.coco.loadAnns(ann_ids)
            num_persons = len(img_anns)
            filename = self.coco.imgs[img_id]['file_name']
            width = self.coco.imgs[img_id]['width']
            height = self.coco.imgs[img_id]['height']
            json_dict['height'] = height
            json_dict['width'] = width



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--save_dir', default=None, type=str,
                        dest='save_dir', help='The directory to save the data.')
    parser.add_argument('--ori_img_dir', default=None, type=str,
                        dest='ori_img_dir', help='The directory of the image data.')
    parser.add_argument('--anno_file', default=None, type=str,
                        dest='anno_file', help='The annotation file.')

    args = parser.parse_args()

    coco_det_generator = CocoDetGenerator(args)
    coco_det_generator.generate_label()