# -*- coding: utf-8 -*-
"""Text_Generation_model

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1b-m1Lv1hYna_OE8bTy7ElXJChjYeSDAk
"""

import numpy as np
import pandas as pd
from gensim.models import Word2Vec, word2vec

import os
import sys
from os import path
from shutil import copy
import gc

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.layers import Embedding
from tensorflow.keras.optimizers import RMSprop, Adam
from tensorflow.keras import regularizers

base_path = "drive/My Drive/text_generation/"

device_name = tf.test.gpu_device_name()
if device_name:
    print('Found GPU at: {}'.format(device_name))

# write char-based segmentation result to txt file
output = open(path.join(base_path, "c_chat_char.txt"), 'w', encoding='utf-8')

# text_1.txt is a part of the crawler output
with open(path.join(base_path, "text_1.txt"), 'r', encoding='utf-8') as content:
    for texts_num, line in enumerate(content):
        line = line.strip('\n')
        chars = [c for c in line]

        output.write(" ".join(chars) + "\n")

        if (texts_num + 1) % 20000 == 0:
            print("finished {} lines.".format(texts_num + 1))
    
output.close()

# train word2vec with crawled data
sentences = word2vec.LineSentence(path.join(base_path, "c_chat_char.txt"))
word2vec_256 = Word2Vec(sentences, size=256, sg=1, iter=7, sorted_vocab=1, hs=1, min_count=15)
word2vec_256.save(path.join(base_path,"word2vec_256.model"))

# load pretrained model
word2vec_model = Word2Vec.load(path.join(base_path, "word2vec_256.model"))

# build word lookup matrix
word_count = dict()
for v in word2vec_model.wv.vocab:
    word_count[v] = word2vec_model.wv.vocab[v].count

sorted_word_count = dict(sorted(word_count.items(), key = lambda x: x[1], reverse=True))

sorted_vocabs = list(sorted_word_count.keys())

char_to_id = {w: i for (i, w) in enumerate(sorted_vocabs)}
char_to_id[' '] = 0

id_to_char = {i: w for (w, i) in char_to_id.items()}
n_vocab = len(char_to_id)

print("Vocabulary Size: ", n_vocab)

file_path = path.join(base_path, "text_1.txt")
text = ""
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()
    text = text.encode('utf-8').decode('utf-8-sig')

text_as_int = np.array([char_to_id.get(c, 0) for c in text])

seq_len = 30
char_dataset = tf.data.Dataset.from_tensor_slices(text_as_int)
sequences = char_dataset.batch(seq_len+1, drop_remainder=True)

def split_input_target(chunk):
    input_text = chunk[:-1]
    target_text = chunk[1:]
    return input_text, target_text

dataset = sequences.map(split_input_target)

BUFFER_SIZE = 20000
BATCH_SIZE=32

dataset = dataset.shuffle(BUFFER_SIZE).batch(BATCH_SIZE, drop_remainder=True)

vocab_size = n_vocab
embedding_dim = 256
LSTM_units = 768

def get_weight_matrix(embedding, word2id_dict, embedding_dim):
    weight_matrix = np.zeros((vocab_size, embedding_dim))
    for word, i in word2id_dict.items():
        try:
            weight_matrix[i] = embedding.get_vector(word)
        except:
            weight_matrix[i] = np.zeros(embedding_dim)
    return weight_matrix

# use pretrained word vector
embedding_matrix = get_weight_matrix(word2vec_model.wv, char_to_id, embedding_dim)

def build_LSTM(vocab_size, embedding_dim, batch_size, return_sequences):
    model = Sequential()
    embedding_layer = Embedding(vocab_size, 256, weights=[embedding_matrix], batch_input_shape=[batch_size, None], trainable=False)
    model.add(embedding_layer)
    model.add(LSTM(LSTM_units, return_sequences=return_sequences, stateful=True))
    model.add(Dense(vocab_size))
    return model

def loss(labels, logits):
    return tf.keras.losses.sparse_categorical_crossentropy(labels, logits, from_logits=True)

ckp_dir = path.join(base_path, "training_checkpoints")
ckp_path = path.join(ckp_dir, "cp.ckpt")

ckp_callback=tf.keras.callbacks.ModelCheckpoint(
    filepath=ckp_path,
    save_weights_only=True)

model = build_LSTM(vocab_size, embedding_dim, BATCH_SIZE, return_sequences=True)
model.compile(optimizer='adam', loss=loss)

# if a checkpoint exists, we can start the training from here
print("latest checkpoint: ", tf.train.latest_checkpoint(ckp_dir))
model.load_weights(tf.train.latest_checkpoint(ckp_dir))

# model training
model.fit(dataset, epochs=50, callbacks=[ckp_callback])

def generate_seq(model, input_seed, n_char):
    text_generated = []
    model.reset_states()

    input_eval = [char_to_id[s] for s in input_seed]
    input_eval = tf.expand_dims(input_eval, 0)

    for i in range(n_char):
        predictions = model(input_eval)
        predictions = tf.squeeze(predictions, 0)
        predicted_id = tf.random.categorical(predictions, num_samples=1)[-1,0].numpy()

        input_eval = tf.expand_dims([predicted_id], 0)

        text_generated.append(id_to_char[predicted_id])
    
    result = input_seed + ''.join(text_generated)
    return result

gen_model = build_LSTM(vocab_size, embedding_dim, batch_size=1, return_sequences=True)
model.load_weights(tf.train.latest_checkpoint(ckp_dir))
gen_model.set_weights(model.get_weights())

generate_seq(gen_model, "爽啦", 20)