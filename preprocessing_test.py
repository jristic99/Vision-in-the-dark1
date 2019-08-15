from __future__ import division
import os, time, scipy.io
#import tensorflow as tf
from tensorflow import keras 
from keras import layers 
from keras import models
import numpy as np
import rawpy
import glob
from tensorflow import device


input_dir = './dataset/Fuji/short/'
gt_dir = './dataset/Fuji/long/'


# get train IDs
test_fns = glob.glob(gt_dir + '1*.RAF')
test_ids = [int(os.path.basename(test_fn)[0:5]) for test_fn in test_fns]
in_images = {}
in_images['300'] = [None] * len(test_ids)
in_images['250'] = [None] * len(test_ids)
in_images['100'] = [None] * len(test_ids)

def dts(x):
    import tensorflow as tf 
    return tf.depth_to_space(x,3)


def conv2d_block(input_tensor, n_filters, kernel_size = 3, batchnorm = True):
    """Function to add 2 convolutional layers with the parameters passed to it"""
    # first layer
    x = layers.Conv2D(filters = n_filters, kernel_size = (kernel_size, kernel_size), kernel_initializer = 'random_uniform', padding = 'same')(input_tensor)
    if batchnorm:
        x = layers.BatchNormalization()(x)
    x = layers.Activation('relu')(x)
    
    # second layer
    x = layers.Conv2D(filters = n_filters, kernel_size = (kernel_size, kernel_size),\
                kernel_initializer = 'he_normal', padding = 'same')(x)
    if batchnorm:
        x = layers.BatchNormalization()(x)
    x = layers.Activation('relu')(x)
    
    return x

def get_unet(n_filters = 16, dropout = 0.1, batchnorm = False):
    # nismo sigurne da li treba raditi batch norm 
    # potencijalno n_filters = 32

    # Contracting Path
    input_layer = layers.Input(shape=(512,512,9))
    c1 = conv2d_block(input_layer, n_filters * 1, kernel_size = 3, batchnorm = batchnorm)
    p1 = layers.MaxPooling2D((2, 2))(c1)
    #p1 = Dropout(dropout)(p1)
    
    c2 = conv2d_block(p1, n_filters * 2, kernel_size = 3, batchnorm = batchnorm)
    p2 = layers.MaxPooling2D((2, 2))(c2)
    #p2 = Dropout(dropout)(p2)
    
    c3 = conv2d_block(p2, n_filters * 4, kernel_size = 3, batchnorm = batchnorm)
    p3 = layers.MaxPooling2D((2, 2))(c3)
    #p3 = Dropout(dropout)(p3)
    
    c4 = conv2d_block(p3, n_filters * 8, kernel_size = 3, batchnorm = batchnorm)
    p4 = layers.MaxPooling2D((2, 2))(c4)
    #p4 = Dropout(dropout)(p4)
    
    c5 = conv2d_block(p4, n_filters = n_filters * 16, kernel_size = 3, batchnorm = batchnorm)
    
    # Expansive Path #pool size je u radu 2, potencijalno je greska = kernel size==pool size 
    u6 = layers.Conv2DTranspose(n_filters * 8, (3, 3), strides = (2, 2), padding = 'same')(c5)
    u6 = layers.concatenate([u6, c4])
    #u6 = Dropout(dropout)(u6)
    c6 = conv2d_block(u6, n_filters * 8, kernel_size = 3, batchnorm = batchnorm)
    
    u7 = layers.Conv2DTranspose(n_filters * 4, (3, 3), strides = (2, 2), padding = 'same')(c6)
    u7 = layers.concatenate([u7, c3])
    #u7 = Dropout(dropout)(u7)
    c7 = conv2d_block(u7, n_filters * 4, kernel_size = 3, batchnorm = batchnorm)
    
    u8 = layers.Conv2DTranspose(n_filters * 2, (3, 3), strides = (2, 2), padding = 'same')(c7)
    u8 = layers.concatenate([u8, c2])
    #u8 = Dropout(dropout)(u8)
    c8 = conv2d_block(u8, n_filters * 2, kernel_size = 3, batchnorm = batchnorm)
    
    u9 = layers.Conv2DTranspose(n_filters * 1, (3, 3), strides = (2, 2), padding = 'same')(c8)
    u9 = layers.concatenate([u9, c1])
    #u9 = Dropout(dropout)(u9)
    c9 = conv2d_block(u9, n_filters * 1, kernel_size = 3, batchnorm = batchnorm)
    
    c9 = layers.Conv2D(27, (1, 1), activation=None)(c9)
    #outputs = tf.depth_to_space(c9, 3)
    
    outputs = layers.Lambda(dts)(c9)
    model = models.Model(inputs=input_layer, outputs=outputs)
    return model


def pack_raw(raw):
    # pack X-Trans image to 9 channels
    im = raw.raw_image_visible.astype(np.float32)
    im = np.maximum(im - 1024, 0) / (16383 - 1024)  # subtract the black level

    img_shape = im.shape
    H = (img_shape[0] // 6) * 6
    W = (img_shape[1] // 6) * 6

    out = np.zeros((H // 3, W // 3, 9))

    # 0 R
    out[0::2, 0::2, 0] = im[0:H:6, 0:W:6]
    out[0::2, 1::2, 0] = im[0:H:6, 4:W:6]
    out[1::2, 0::2, 0] = im[3:H:6, 1:W:6]
    out[1::2, 1::2, 0] = im[3:H:6, 3:W:6]

    # 1 G
    out[0::2, 0::2, 1] = im[0:H:6, 2:W:6]
    out[0::2, 1::2, 1] = im[0:H:6, 5:W:6]
    out[1::2, 0::2, 1] = im[3:H:6, 2:W:6]
    out[1::2, 1::2, 1] = im[3:H:6, 5:W:6]

    # 1 B
    out[0::2, 0::2, 2] = im[0:H:6, 1:W:6]
    out[0::2, 1::2, 2] = im[0:H:6, 3:W:6]
    out[1::2, 0::2, 2] = im[3:H:6, 0:W:6]
    out[1::2, 1::2, 2] = im[3:H:6, 4:W:6]

    # 4 R
    out[0::2, 0::2, 3] = im[1:H:6, 2:W:6]
    out[0::2, 1::2, 3] = im[2:H:6, 5:W:6]
    out[1::2, 0::2, 3] = im[5:H:6, 2:W:6]
    out[1::2, 1::2, 3] = im[4:H:6, 5:W:6]

    # 5 B
    out[0::2, 0::2, 4] = im[2:H:6, 2:W:6]
    out[0::2, 1::2, 4] = im[1:H:6, 5:W:6]
    out[1::2, 0::2, 4] = im[4:H:6, 2:W:6]
    out[1::2, 1::2, 4] = im[5:H:6, 5:W:6]

    out[:, :, 5] = im[1:H:3, 0:W:3]
    out[:, :, 6] = im[1:H:3, 1:W:3]
    out[:, :, 7] = im[2:H:3, 0:W:3]
    out[:, :, 8] = im[2:H:3, 1:W:3]
    return out


test_list = []
gt_list = []

with device('/cpu:0'):
    for test_id in test_ids: 
        # insert test example to test_list
        in_files = glob.glob(input_dir + '%05d_00*.RAF' % test_id)
        for k in range(len(in_files)):   #for k in range(len(in_files)):
            print(k)
            in_path = in_files[k]
            in_fn = os.path.basename(in_path)
            gt_files = glob.glob(gt_dir + '%05d_00*.RAF' % test_id)
            gt_path = gt_files[0]
            gt_fn = os.path.basename(gt_path)
            in_exposure = float(in_fn[9:-5])
            gt_exposure = float(gt_fn[9:-5])
            ratio = min(gt_exposure / in_exposure, 300)
            ps = 512 

            
            raw = rawpy.imread(in_path)
            input_full = np.expand_dims(pack_raw(raw), axis=0) * ratio
            
            
            im = raw.postprocess(use_camera_wb=True, half_size=False, no_auto_bright=True, output_bps=16)
            # scale_full = np.expand_dims(np.float32(im/65535.0),axis = 0)*ratio #scale the low-light image using the same ratio
            scale_full = np.expand_dims(np.float32(im / 65535.0), axis=0)

            gt_raw = rawpy.imread(gt_path)
            im = gt_raw.postprocess(use_camera_wb=True, half_size=False, no_auto_bright=True, output_bps=16)
            gt_full = np.expand_dims(np.float32(im / 65535.0), axis=0)
            
            # crop
            
            H = input_full.shape[1]
            W = input_full.shape[2]

            #H = 1536
            #W = 1536

            xx = np.random.randint(0, W - ps)
            yy = np.random.randint(0, H - ps)
            input_full = input_full[:, yy:yy + ps, xx:xx + ps, :]
            gt_full = gt_full[:, yy * 3:yy * 3 + ps * 3, xx * 3:xx * 3 + ps * 3, :]

            input_full = np.minimum(input_full, 1.0)
            test_list.append(input_full)
            gt_list.append(gt_full)

    print('done preprocessing')
    test_list = np.asarray(test_list)
    gt_list = np.asarray(gt_list)

    test_list = test_list[:,0,:,:,:]
    gt_list = gt_list[:,0,:,:,:]

    np.save('test_list.npy', test_list)
    print('done saving')
    np.save('gt_list.npy', gt_list)