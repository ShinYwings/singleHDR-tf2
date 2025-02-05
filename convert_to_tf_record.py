import tensorflow as tf
import numpy as np
import os
import glob
import cv2

TFRECORD_OPTION = tf.io.TFRecordOptions(compression_type="GZIP")

def bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

patch_size = 256
patch_stride = 64
batch_size = 32
count = 0

def run(args):
    out_dir = f'tf_records/{patch_size}_{patch_stride}_b{batch_size}_tfrecords'

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    cur_writing_path = os.path.join(out_dir, "train_{:d}_{:04d}.tfrecords".format(patch_stride, 0))

    HDRs_512 = sorted(glob.glob(f'{args.dir}/HDR_gt/*.hdr'))
    LDRs_512 = sorted(glob.glob(f'{args.dir}/LDR_in/*.jpg'))

    for i, scene_dir in enumerate(HDRs_512):
        if (i % 10 == 0):
            print(f'{i}/{len(HDRs_512)}')

        # read images
        ref_HDR = cv2.imread(HDRs_512[i], -1).astype(np.float32)  # read raw values
        ref_LDR = cv2.imread(LDRs_512[i]).astype(np.float32)   # read jpg

        h, w, c = ref_HDR.shape

        def write_example(h1, h2, w1, w2):
            global count
            global writer

            cur_batch_index = count // batch_size

            if count % batch_size == 0:
                writer.close()
                cur_writing_path = os.path.join(out_dir,
                                                "train_{:d}_{:04d}.tfrecords".format(patch_stride, cur_batch_index))
                writer = tf.io.TFRecordWriter(cur_writing_path, TFRECORD_OPTION)

            ref_HDR_patch = ref_HDR[h1:h2, w1:w2, ::-1]
            ref_LDR_patch = ref_LDR[h1:h2, w1:w2, ::-1]

            """extreme cases filtering"""
            ref_LDR_patch_gray = cv2.cvtColor(ref_LDR_patch, cv2.COLOR_RGB2GRAY)
            extreme_pixels = np.sum(ref_LDR_patch_gray >= 249.0) + np.sum(ref_LDR_patch_gray <= 6.0)
            if extreme_pixels <= 256*256//2:
                print('pass')

                count += 1

                # create example
                example = tf.train.Example(features=tf.train.Features(feature={
                    'ref_HDR': bytes_feature(ref_HDR_patch.tostring()),
                    'ref_LDR': bytes_feature(ref_LDR_patch.tostring()),
                }))
                writer.write(example.SerializeToString())
            else:
                print('filtered out')


        # generate patches
        for h_ in range(0, h - patch_size + 1, patch_stride):
            for w_ in range(0, w - patch_size + 1, patch_stride):
                write_example(h_, h_ + patch_size, w_, w_ + patch_size)

        # deal with border patch
        if h % patch_size:
            for w_ in range(0, w - patch_size + 1, patch_stride):
                write_example(h - patch_size, h, w_, w_ + patch_size)

        if w % patch_size:
            for h_ in range(0, h - patch_size + 1, patch_stride):
                write_example(h_, h_ + patch_size, w - patch_size, w)

        if w % patch_size and h % patch_size:
            write_example(h - patch_size, h, w - patch_size, w)

    writer.close()
    print("Finished!\nTotal number of patches:", count)

if __name__=="__main__":
    
    import argparse
    
    parser = argparse.ArgumentParser(description="cvt to tfrecord")
    parser.add_argument('--dir', type=str) 
    args = parser.parse_args
    
    run(args)