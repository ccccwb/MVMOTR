# ------------------------------------------------------------------------
# Copyright (c) 2021 megvii-model. All Rights Reserved.
# ------------------------------------------------------------------------
# Modified from Deformable DETR (https://github.com/fundamentalvision/Deformable-DETR)
# Copyright (c) 2020 SenseTime. All Rights Reserved.
# ------------------------------------------------------------------------
# Modified from DETR (https://github.com/facebookresearch/detr)
# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
# ------------------------------------------------------------------------

"""
Transforms and data augmentation for both image + bbox.
"""
import copy
import random
import PIL
import torch
import torchvision.transforms as T
import torchvision.transforms.functional as F
from PIL import Image, ImageDraw
from util.box_ops import box_xyxy_to_cxcywh
from util.misc import interpolate
import numpy as np
import os 



def crop_mot(image, target, region):
    cropped_image = F.crop(image, *region)

    target = target.copy()
    i, j, h, w = region

    # should we do something wrt the original size?
    target["size"] = torch.tensor([h, w])

    fields = ["labels", "area", "iscrowd", "obj_ids"]

    if "boxes" in target:
        boxes = target["boxes"]
        cropped_boxes = boxes - torch.as_tensor([j, i, j, i])
        target["boxes"] = cropped_boxes.reshape(-1, 4)
        fields.append("boxes")

    if "masks" in target:
        # FIXME should we update the area here if there are no boxes?
        target['masks'] = target['masks'][:, i:i + h, j:j + w]
        fields.append("masks")

    # remove elements for which the boxes or masks that have zero area
    if "boxes" in target or "masks" in target:
        # favor boxes selection when defining which elements to keep
        # this is compatible with previous implementation
        if "boxes" in target:
            cropped_boxes = target['boxes'].reshape(-1, 2, 2)
            max_size = torch.as_tensor([w, h], dtype=torch.float32)
            cropped_boxes = torch.min(cropped_boxes.reshape(-1, 2, 2), max_size)
            cropped_boxes = cropped_boxes.clamp(min=0)
            keep = torch.all(cropped_boxes[:, 1, :] > cropped_boxes[:, 0, :], dim=1)
        else:
            keep = target['masks'].flatten(1).any(1)

        for field in fields:
            target[field] = target[field][keep]

    return cropped_image, target

def crop_mot_multiview(image_1, image_2, target, region):
    cropped_image_1 = F.crop(image_1, *region)
    cropped_image_2 = F.crop(image_2, *region)
    target = target.copy()
    i, j, h, w = region

    # should we do something wrt the original size?
    target["size"] = torch.tensor([h, w])

    fields = ["labels", "area", "iscrowd", "obj_ids"]
    fields_2 = ["area_2", "iscrowd_2", "obj_ids_2"]

    if "boxes" in target:
        boxes = target["boxes"]
        cropped_boxes = boxes - torch.as_tensor([j, i, j, i])
        target["boxes"] = cropped_boxes.reshape(-1, 4)
        fields.append("boxes")
        
        boxes = target["boxes_2"]
        cropped_boxes = boxes - torch.as_tensor([j, i, j, i])
        target["boxes_2"] = cropped_boxes.reshape(-1, 4)
        fields_2.append("boxes_2")

    if "masks" in target:
        # FIXME should we update the area here if there are no boxes?
        target['masks'] = target['masks'][:, i:i + h, j:j + w]
        fields.append("masks")

    # remove elements for which the boxes or masks that have zero area
    if "boxes" in target or "masks" in target:
        # favor boxes selection when defining which elements to keep
        # this is compatible with previous implementation
        if "boxes" in target:
            cropped_boxes = target['boxes'].reshape(-1, 2, 2)
            max_size = torch.as_tensor([w, h], dtype=torch.float32)
            cropped_boxes = torch.min(cropped_boxes.reshape(-1, 2, 2), max_size)
            cropped_boxes = cropped_boxes.clamp(min=0)
            keep = torch.all(cropped_boxes[:, 1, :] > cropped_boxes[:, 0, :], dim=1)
            
            cropped_boxes_2 = target['boxes_2'].reshape(-1, 2, 2)
            cropped_boxes_2 = torch.min(cropped_boxes_2.reshape(-1, 2, 2), max_size)
            cropped_boxes_2 = cropped_boxes_2.clamp(min=0)
            keep2 = torch.all(cropped_boxes_2[:, 1, :] > cropped_boxes_2[:, 0, :], dim=1)
            
        else:
            keep = target['masks'].flatten(1).any(1)

        for field in fields:
            target[field] = target[field][keep]
        for field in fields_2:
            target[field] = target[field][keep2]

    return cropped_image_1, cropped_image_2, target

def random_shift(image, target, region, sizes):
    oh, ow = sizes
    # step 1, shift crop and re-scale image firstly
    cropped_image = F.crop(image, *region)
    cropped_image = F.resize(cropped_image, sizes)

    target = target.copy()
    i, j, h, w = region

    # should we do something wrt the original size?
    target["size"] = torch.tensor([h, w])

    fields = ["labels", "area", "iscrowd", "obj_ids"]

    if "boxes" in target:
        boxes = target["boxes"]
        cropped_boxes = boxes - torch.as_tensor([j, i, j, i])
        cropped_boxes *= torch.as_tensor([ow / w, oh / h, ow / w, oh / h])
        target["boxes"] = cropped_boxes.reshape(-1, 4)
        fields.append("boxes")

    if "masks" in target:
        # FIXME should we update the area here if there are no boxes?
        target['masks'] = target['masks'][:, i:i + h, j:j + w]
        fields.append("masks")

    # remove elements for which the boxes or masks that have zero area
    if "boxes" in target or "masks" in target:
        # favor boxes selection when defining which elements to keep
        # this is compatible with previous implementation
        if "boxes" in target:
            cropped_boxes = target['boxes'].reshape(-1, 2, 2)
            max_size = torch.as_tensor([w, h], dtype=torch.float32)
            cropped_boxes = torch.min(cropped_boxes.reshape(-1, 2, 2), max_size)
            cropped_boxes = cropped_boxes.clamp(min=0)
            keep = torch.all(cropped_boxes[:, 1, :] > cropped_boxes[:, 0, :], dim=1)
        else:
            keep = target['masks'].flatten(1).any(1)

        for field in fields:
            target[field] = target[field][keep]

    return cropped_image, target


def crop(image, target, region):
    cropped_image = F.crop(image, *region)

    target = target.copy()
    i, j, h, w = region

    # should we do something wrt the original size?
    target["size"] = torch.tensor([h, w])

    fields = ["labels", "area", "iscrowd"]
    if 'obj_ids' in target:
        fields.append('obj_ids')

    if "boxes" in target:
        boxes = target["boxes"]
        max_size = torch.as_tensor([w, h], dtype=torch.float32)
        cropped_boxes = boxes - torch.as_tensor([j, i, j, i])
        cropped_boxes = torch.min(cropped_boxes.reshape(-1, 2, 2), max_size)
        cropped_boxes = cropped_boxes.clamp(min=0)

        area = (cropped_boxes[:, 1, :] - cropped_boxes[:, 0, :]).prod(dim=1)
        target["boxes"] = cropped_boxes.reshape(-1, 4)
        target["area"] = area
        fields.append("boxes")

    if "masks" in target:
        # FIXME should we update the area here if there are no boxes?
        target['masks'] = target['masks'][:, i:i + h, j:j + w]
        fields.append("masks")

    # remove elements for which the boxes or masks that have zero area
    if "boxes" in target or "masks" in target:
        # favor boxes selection when defining which elements to keep
        # this is compatible with previous implementation
        if "boxes" in target:
            cropped_boxes = target['boxes'].reshape(-1, 2, 2)
            keep = torch.all(cropped_boxes[:, 1, :] > cropped_boxes[:, 0, :], dim=1)
        else:
            keep = target['masks'].flatten(1).any(1)

        for field in fields:
            target[field] = target[field][keep]

    return cropped_image, target


def hflip(image, target):
    flipped_image = F.hflip(image)

    w, h = image.size

    target = target.copy()
    if "boxes" in target:
        boxes = target["boxes"]
        boxes = boxes[:, [2, 1, 0, 3]] * torch.as_tensor([-1, 1, -1, 1]) + torch.as_tensor([w, 0, w, 0])
        target["boxes"] = boxes

    if "masks" in target:
        target['masks'] = target['masks'].flip(-1)

    return flipped_image, target

def hflip_multiview(image_1, image_2, target):
    flipped_image_1 = F.hflip(image_1)
    flipped_image_2 = F.hflip(image_2)

    w, h = image_1.size

    target = target.copy()
    if "boxes" in target:
        boxes = target["boxes"]
        boxes = boxes[:, [2, 1, 0, 3]] * torch.as_tensor([-1, 1, -1, 1]) + torch.as_tensor([w, 0, w, 0])
        target["boxes"] = boxes
        
        boxes = target["boxes_2"]
        boxes = boxes[:, [2, 1, 0, 3]] * torch.as_tensor([-1, 1, -1, 1]) + torch.as_tensor([w, 0, w, 0])
        target["boxes_2"] = boxes

    if "masks" in target:
        target['masks'] = target['masks'].flip(-1)

    return flipped_image_1, flipped_image_2, target

def resize(image, target, size, max_size=None):
    # size can be min_size (scalar) or (w, h) tuple

    def get_size_with_aspect_ratio(image_size, size, max_size=None):
        w, h = image_size
        if max_size is not None:
            min_original_size = float(min((w, h)))
            max_original_size = float(max((w, h)))
            if max_original_size / min_original_size * size > max_size:
                size = int(round(max_size * min_original_size / max_original_size))

        if (w <= h and w == size) or (h <= w and h == size):
            return (h, w)

        if w < h:
            ow = size
            oh = int(size * h / w)
        else:
            oh = size
            ow = int(size * w / h)

        return (oh, ow)

    def get_size(image_size, size, max_size=None):
        if isinstance(size, (list, tuple)):
            return size[::-1]
        else:
            return get_size_with_aspect_ratio(image_size, size, max_size)

    size = get_size(image.size, size, max_size)
    rescaled_image = F.resize(image, size)

    if target is None:
        return rescaled_image, None

    ratios = tuple(float(s) / float(s_orig) for s, s_orig in zip(rescaled_image.size, image.size))
    ratio_width, ratio_height = ratios

    target = target.copy()
    if "boxes" in target:
        boxes = target["boxes"]
        scaled_boxes = boxes * torch.as_tensor([ratio_width, ratio_height, ratio_width, ratio_height])
        target["boxes"] = scaled_boxes

    if "area" in target:
        area = target["area"]
        scaled_area = area * (ratio_width * ratio_height)
        target["area"] = scaled_area

    h, w = size
    target["size"] = torch.tensor([h, w])

    if "masks" in target:
        target['masks'] = interpolate(
            target['masks'][:, None].float(), size, mode="nearest")[:, 0] > 0.5

    return rescaled_image, target

def resize_multiview(image_1, image_2, target, size, max_size=None):
    # size can be min_size (scalar) or (w, h) tuple

    def get_size_with_aspect_ratio(image_size, size, max_size=None):
        w, h = image_size
        if max_size is not None:
            min_original_size = float(min((w, h)))
            max_original_size = float(max((w, h)))
            if max_original_size / min_original_size * size > max_size:
                size = int(round(max_size * min_original_size / max_original_size))

        if (w <= h and w == size) or (h <= w and h == size):
            return (h, w)

        if w < h:
            ow = size
            oh = int(size * h / w)
        else:
            oh = size
            ow = int(size * w / h)

        return (oh, ow)

    def get_size(image_size, size, max_size=None):
        if isinstance(size, (list, tuple)):
            return size[::-1]
        else:
            return get_size_with_aspect_ratio(image_size, size, max_size)
    
    size = get_size(image_1.size, size, max_size)
    rescaled_image_1 = F.resize(image_1, size)
    rescaled_image_2 = F.resize(image_2, size)
    if target is None:
        return rescaled_image, None

    ratios = tuple(float(s) / float(s_orig) for s, s_orig in zip(rescaled_image_1.size, image_1.size))
    ratio_width, ratio_height = ratios

    target = target.copy()
    if "boxes" in target:
        boxes = target["boxes"]
        scaled_boxes = boxes * torch.as_tensor([ratio_width, ratio_height, ratio_width, ratio_height])
        target["boxes"] = scaled_boxes
        
        boxes = target["boxes_2"]
        scaled_boxes = boxes * torch.as_tensor([ratio_width, ratio_height, ratio_width, ratio_height])
        target["boxes_2"] = scaled_boxes

    if "area" in target:
        area = target["area"]
        scaled_area = area * (ratio_width * ratio_height)
        target["area"] = scaled_area
        
        area = target["area_2"]
        scaled_area = area * (ratio_width * ratio_height)
        target["area_2"] = scaled_area

    h, w = size
    target["size"] = torch.tensor([h, w])

    if "masks" in target:
        target['masks'] = interpolate(
            target['masks'][:, None].float(), size, mode="nearest")[:, 0] > 0.5

    return rescaled_image_1, rescaled_image_2, target

def pad(image, target, padding):
    # assumes that we only pad on the bottom right corners
    padded_image = F.pad(image, (0, 0, padding[0], padding[1]))
    if target is None:
        return padded_image, None
    target = target.copy()
    # should we do something wrt the original size?
    target["size"] = torch.tensor(padded_image[::-1])
    if "masks" in target:
        target['masks'] = torch.nn.functional.pad(target['masks'], (0, padding[0], 0, padding[1]))
    return padded_image, target


class RandomCrop(object):
    def __init__(self, size):
        self.size = size

    def __call__(self, img, target):
        region = T.RandomCrop.get_params(img, self.size)
        return crop(img, target, region)


class MotRandomCrop(RandomCrop):
    def __call__(self, imgs: list, targets: list):
        ret_imgs = []
        ret_targets = []
        region = T.RandomCrop.get_params(imgs[0], self.size)
        for img_i, targets_i in zip(imgs, targets):
            img_i, targets_i = crop(img_i, targets_i, region)
            ret_imgs.append(img_i)
            ret_targets.append(targets_i)
        return ret_imgs, ret_targets

class FixedMotRandomCrop(object):
    def __init__(self, min_size: int, max_size: int):
        self.min_size = min_size
        self.max_size = max_size

    def __call__(self, imgs: list, targets: list):
        ret_imgs = []
        ret_targets = []
        w = random.randint(self.min_size, min(imgs[0].width, self.max_size))
        h = random.randint(self.min_size, min(imgs[0].height, self.max_size))
        region = T.RandomCrop.get_params(imgs[0], [h, w])
        for img_i, targets_i in zip(imgs, targets):
            img_i, targets_i = crop_mot(img_i, targets_i, region)
            ret_imgs.append(img_i)
            ret_targets.append(targets_i)
        return ret_imgs, ret_targets
    
class MultiviewFixedMotRandomCrop(object):
    def __init__(self, min_size: int, max_size: int):
        self.min_size = min_size
        self.max_size = max_size

    def __call__(self, imgs: list, targets: list):
        ret_imgs = []
        ret_targets = []
        imgs_1, imgs_2 = imgs
        w = random.randint(self.min_size, min(imgs_1[0].width, self.max_size))
        h = random.randint(self.min_size, min(imgs_1[0].height, self.max_size))
        region = T.RandomCrop.get_params(imgs_1[0], [h, w])

        for img_1_i, img_2_i, targets_i in zip(imgs_1, imgs_2, targets):
            img_1_i, img_2_i, targets_i = crop_mot_multiview(img_1_i, img_2_i, targets_i, region)
            ret_imgs.append([img_1_i, img_2_i])
            ret_targets.append(targets_i)
            
        return ret_imgs, ret_targets

class MotRandomShift(object):
    def __init__(self, bs=1):
        self.bs = bs

    def __call__(self, imgs: list, targets: list):
        ret_imgs = copy.deepcopy(imgs)
        ret_targets = copy.deepcopy(targets)

        n_frames = len(imgs)
        select_i = random.choice(list(range(n_frames)))
        w, h = imgs[select_i].size

        xshift = (100 * torch.rand(self.bs)).int()
        xshift *= (torch.randn(self.bs) > 0.0).int() * 2 - 1 
        yshift = (100 * torch.rand(self.bs)).int()
        yshift *= (torch.randn(self.bs) > 0.0).int() * 2 - 1
        ymin = max(0, -yshift[0])
        ymax = min(h, h - yshift[0])
        xmin = max(0, -xshift[0])
        xmax = min(w, w - xshift[0])

        region = (int(ymin), int(xmin), int(ymax-ymin), int(xmax-xmin))
        ret_imgs[select_i], ret_targets[select_i] = random_shift(imgs[select_i], targets[select_i], region, (h,w)) 
        
        return ret_imgs, ret_targets


class FixedMotRandomShift(object):
    def __init__(self, bs=1, padding=50):
        self.bs = bs
        self.padding = padding

    def __call__(self, imgs: list, targets: list):
        ret_imgs = []
        ret_targets = []

        n_frames = len(imgs)
        w, h = imgs[0].size
        xshift = (self.padding * torch.rand(self.bs)).int() + 1
        xshift *= (torch.randn(self.bs) > 0.0).int() * 2 - 1
        yshift = (self.padding * torch.rand(self.bs)).int() + 1
        yshift *= (torch.randn(self.bs) > 0.0).int() * 2 - 1
        ret_imgs.append(imgs[0])
        ret_targets.append(targets[0])
        for i in range(1, n_frames):
            ymin = max(0, -yshift[0])
            ymax = min(h, h - yshift[0])
            xmin = max(0, -xshift[0])
            xmax = min(w, w - xshift[0])
            prev_img = ret_imgs[i-1].copy()
            prev_target = copy.deepcopy(ret_targets[i-1])
            region = (int(ymin), int(xmin), int(ymax - ymin), int(xmax - xmin))
            img_i, target_i = random_shift(prev_img, prev_target, region, (h, w))
            ret_imgs.append(img_i)
            ret_targets.append(target_i)

        return ret_imgs, ret_targets


class RandomSizeCrop(object):
    def __init__(self, min_size: int, max_size: int):
        self.min_size = min_size
        self.max_size = max_size

    def __call__(self, img: PIL.Image.Image, target: dict):
        w = random.randint(self.min_size, min(img.width, self.max_size))
        h = random.randint(self.min_size, min(img.height, self.max_size))
        region = T.RandomCrop.get_params(img, [h, w])
        return crop(img, target, region)


class MotRandomSizeCrop(RandomSizeCrop):
    def __call__(self, imgs, targets):
        w = random.randint(self.min_size, min(imgs[0].width, self.max_size))
        h = random.randint(self.min_size, min(imgs[0].height, self.max_size))
        region = T.RandomCrop.get_params(imgs[0], [h, w])
        ret_imgs = []
        ret_targets = []
        for img_i, targets_i in zip(imgs, targets):
            img_i, targets_i = crop(img_i, targets_i, region)
            ret_imgs.append(img_i)
            ret_targets.append(targets_i)
        return ret_imgs, ret_targets


class CenterCrop(object):
    def __init__(self, size):
        self.size = size

    def __call__(self, img, target):
        image_width, image_height = img.size
        crop_height, crop_width = self.size
        crop_top = int(round((image_height - crop_height) / 2.))
        crop_left = int(round((image_width - crop_width) / 2.))
        return crop(img, target, (crop_top, crop_left, crop_height, crop_width))


class MotCenterCrop(CenterCrop):
    def __call__(self, imgs, targets):
        image_width, image_height = imgs[0].size
        crop_height, crop_width = self.size
        crop_top = int(round((image_height - crop_height) / 2.))
        crop_left = int(round((image_width - crop_width) / 2.))
        ret_imgs = []
        ret_targets = []
        for img_i, targets_i in zip(imgs, targets):
            img_i, targets_i = crop(img_i, targets_i, (crop_top, crop_left, crop_height, crop_width))
            ret_imgs.append(img_i)
            ret_targets.append(targets_i)
        return ret_imgs, ret_targets


class RandomHorizontalFlip(object):
    def __init__(self, p=0.5):
        self.p = p

    def __call__(self, img, target):
        if random.random() < self.p:
            return hflip(img, target)
        return img, target


class MotRandomHorizontalFlip(RandomHorizontalFlip):
    def __call__(self, imgs, targets):
        if random.random() < self.p:
            ret_imgs = []
            ret_targets = []
            for img_i, targets_i in zip(imgs, targets):
                img_i, targets_i = hflip(img_i, targets_i)
                ret_imgs.append(img_i)
                ret_targets.append(targets_i)
            return ret_imgs, ret_targets
        return imgs, targets

class MultiviewMotRandomHorizontalFlip(RandomHorizontalFlip):
    def __call__(self, imgs, targets):
        imgs_1, imgs_2 = imgs
        if random.random() < self.p:
            ret_imgs = []
            ret_targets = []
            for img_1_i, img_2_i, targets_i in zip(imgs_1, imgs_2, targets):
                img_1_i, img_2_i, targets_i = hflip_multiview(img_1_i, img_2_i, targets_i)
                ret_imgs.append([img_1_i, img_2_i])
                ret_targets.append(targets_i)
            return ret_imgs, ret_targets
        return imgs, targets
    


class RandomResize(object):
    def __init__(self, sizes, max_size=None):
        assert isinstance(sizes, (list, tuple))
        self.sizes = sizes
        self.max_size = max_size

    def __call__(self, img, target=None):
        size = random.choice(self.sizes)
        return resize(img, target, size, self.max_size)


class MotRandomResize(RandomResize):
    def __call__(self, imgs, targets):
        size = random.choice(self.sizes)
        ret_imgs = []
        ret_targets = []
        for img_i, targets_i in zip(imgs, targets):
            img_i, targets_i = resize(img_i, targets_i, size, self.max_size)
            ret_imgs.append(img_i)
            ret_targets.append(targets_i)
        return ret_imgs, ret_targets

class MultiviewMotRandomResize(RandomResize):
    def __call__(self, imgs, targets):
        size = random.choice(self.sizes)
        imgs_1, imgs_2 = imgs

        ret_imgs = []
        ret_targets = []
        for img_1_i, img_2_i, targets_i in zip(imgs_1, imgs_2, targets):
            img_1_i, img_2_i, targets_i = resize_multiview(img_1_i, img_2_i, targets_i, size, self.max_size)
            ret_imgs.append([img_1_i, img_2_i])
            ret_targets.append(targets_i)
        return ret_imgs, ret_targets
    
class RandomPad(object):
    def __init__(self, max_pad):
        self.max_pad = max_pad

    def __call__(self, img, target):
        pad_x = random.randint(0, self.max_pad)
        pad_y = random.randint(0, self.max_pad)
        return pad(img, target, (pad_x, pad_y))


class MotRandomPad(RandomPad):
    def __call__(self, imgs, targets):
        pad_x = random.randint(0, self.max_pad)
        pad_y = random.randint(0, self.max_pad)
        ret_imgs = []
        ret_targets = []
        for img_i, targets_i in zip(imgs, targets):
            img_i, target_i = pad(img_i, targets_i, (pad_x, pad_y))
            ret_imgs.append(img_i)
            ret_targets.append(targets_i)
        return ret_imgs, ret_targets


class RandomSelect(object):
    """
    Randomly selects between transforms1 and transforms2,
    with probability p for transforms1 and (1 - p) for transforms2
    """
    def __init__(self, transforms1, transforms2, p=0.5):
        self.transforms1 = transforms1
        self.transforms2 = transforms2
        self.p = p

    def __call__(self, img, target):
        if random.random() < self.p:
            return self.transforms1(img, target)
        return self.transforms2(img, target)


class MotRandomSelect(RandomSelect):
    """
    Randomly selects between transforms1 and transforms2,
    with probability p for transforms1 and (1 - p) for transforms2
    """
    def __call__(self, imgs, targets):
        if random.random() < self.p:
            return self.transforms1(imgs, targets)
        return self.transforms2(imgs, targets)


class ToTensor(object):
    def __call__(self, img, target):
        return F.to_tensor(img), target


class MotToTensor(ToTensor):
    def __call__(self, imgs, targets):
        ret_imgs = []
        for img in imgs:
            ret_imgs.append(F.to_tensor(img))
        return ret_imgs, targets
    
class MultiviewMotToTensor(ToTensor):
    def __call__(self, imgs, targets):
        ret_imgs = []
        imgs_1, imgs_2 = imgs
        for img_1, img_2 in zip(imgs_1, imgs_2):
            ret_imgs.append([F.to_tensor(img_1), F.to_tensor(img_2)])
        return ret_imgs, targets

class RandomErasing(object):

    def __init__(self, *args, **kwargs):
        self.eraser = T.RandomErasing(*args, **kwargs)

    def __call__(self, img, target):
        return self.eraser(img), target


class MotRandomErasing(RandomErasing):
    def __call__(self, imgs, targets):
        # TODO: Rewrite this part to ensure the data augmentation is same to each image.
        ret_imgs = []
        for img_i, targets_i in zip(imgs, targets):
            ret_imgs.append(self.eraser(img_i))
        return ret_imgs, targets


class MoTColorJitter(T.ColorJitter):
    def __call__(self, imgs, targets):
        transform = self.get_params(self.brightness, self.contrast,
                                    self.saturation, self.hue)
        ret_imgs = []
        for img_i, targets_i in zip(imgs, targets):
            ret_imgs.append(transform(img_i))
        return ret_imgs, targets


class Normalize(object):
    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def __call__(self, image, target=None):
        if target is not None:
            target['ori_img'] = image.clone()
        image = F.normalize(image, mean=self.mean, std=self.std)
        if target is None:
            return image, None
        target = target.copy()
        h, w = image.shape[-2:]
        if "boxes" in target:
            boxes = target["boxes"]
            boxes = box_xyxy_to_cxcywh(boxes)
            boxes = boxes / torch.tensor([w, h, w, h], dtype=torch.float32)
            target["boxes"] = boxes
        return image, target

class MotNormalize(Normalize):
    def __call__(self, imgs, targets=None):
        ret_imgs = []
        ret_targets = []
        for i in range(len(imgs)):
            img_i = imgs[i]
            targets_i = targets[i] if targets is not None else None
            img_i, targets_i = super().__call__(img_i, targets_i)
            ret_imgs.append(img_i)
            ret_targets.append(targets_i)
        return ret_imgs, ret_targets

class MultiviewNormalize(object):
    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def __call__(self, image_1, image_2, target=None):
        
        if target is not None:
            target['ori_img'] = image_1.clone()
            target['ori_img_2'] = image_2.clone()
        image_1 = F.normalize(image_1, mean=self.mean, std=self.std)
        image_2 = F.normalize(image_2, mean=self.mean, std=self.std)
        if target is None:
            return image_1, image_2, None
        target = target.copy()
        h, w = image_1.shape[-2:]
        if "boxes" in target:
            boxes = target["boxes"]
            boxes = box_xyxy_to_cxcywh(boxes)
            boxes = boxes / torch.tensor([w, h, w, h], dtype=torch.float32)
            target["boxes"] = boxes
            
            boxes = target["boxes_2"]
            boxes = box_xyxy_to_cxcywh(boxes)
            boxes = boxes / torch.tensor([w, h, w, h], dtype=torch.float32)
            target["boxes_2"] = boxes
        return image_1, image_2, target

class MultiviewMotNormalize(MultiviewNormalize):
    def __call__(self, imgs, targets=None):
        ret_imgs = []
        ret_targets = []
        imgs_1, imgs_2 = imgs
        for i in range(len(imgs_1)):
            img_1_i = imgs_1[i]
            img_2_i = imgs_2[i]
            targets_i = targets[i] if targets is not None else None
            img_1_i, img_2_i, targets_i = super().__call__(img_1_i, img_2_i, targets_i)
            ret_imgs.append([img_1_i, img_2_i])
            ret_targets.append(targets_i)
        return ret_imgs, ret_targets

class Compose(object):
    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, image, target):
        for t in self.transforms:
            image, target = t(image, target)
        return image, target

    def __repr__(self):
        format_string = self.__class__.__name__ + "("
        for t in self.transforms:
            format_string += "\n"
            format_string += "    {0}".format(t)
        format_string += "\n)"
        return format_string


class MotCompose(Compose):
    def __call__(self, imgs, targets):
        for t in self.transforms:
            imgs, targets = t(imgs, targets)
        return imgs, targets
