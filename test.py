from __future__ import division

### git @ yash0307 ###
import sys,os
import random
import json
import numpy as np
from termcolor import colored
from PIL import Image
import matplotlib.pyplot as plt
from sklearn import svm
from sklearn.externals import joblib
from sklearn.metrics import average_precision_score, accuracy_score
from sklearn import preprocessing
from keras import applications
from keras.preprocessing.image import ImageDataGenerator
from keras import optimizers
from keras.models import Sequential, Model, load_model
from keras.layers import *
from keras.layers.pooling import GlobalAveragePooling1D
from keras.callbacks import LearningRateScheduler
from keras.callbacks import ModelCheckpoint
import keras.backend as K
import keras
import numpy as np
import gym
import sys
import copy
import argparse
from collections import deque
import random

class QNetwork():
    def __init__(self, num_actions, state_size, model_path):
        '''
	    Initialize the class as per input parameters.
            Parameters:
	        environment_name (type string): Name of environment to be used. Possible values: 'CartPole-v0', 'MountainCar-v0', 'SpaceInvaders-v0'
	        model_type (type string): Name of model type to be used. Possible valies: 'linear_dqn', 'dqn', 'ddqn', 'dqn_space_invaders'
	'''
	environment_name = 'DomainAdaptation'
	model_type = 'ddqn'
	self.model = load_model(model_path)

    def load_model(self, model_file):
        '''
	    Given a model file name, loads the model and returns it.
	    Parameters: 
	        model_file (type string): Path of model file to be loaded.
	'''
        print('Loading model....')
        model = load_model(model_file)
        return model

    def get_action(self, state):
        '''
	    Given a state in form of state varialbes, returns the optimal action as per current model.
	    Parameters:
	        state (type numpy array): contains array of size as number of environment state variables.
	'''
        pred_action = self.model.predict(state)
        return np.argmax(pred_action[0])

##### Load Data #####
def data_loader(source_domain, target_domain, num_s_pos_samples, num_reward_samples, data_dir):
	domain_1_reps = np.load(data_dir+'features_from_'+source_domain+'_to_'+source_domain+'.npy')
	domain_2_reps = np.load(data_dir+'features_from_'+source_domain+'_to_'+target_domain+'.npy')
	domain_1_labels = np.load(data_dir+'labels_'+source_domain+'.npy')
	domain_2_labels = np.load(data_dir+'labels_'+target_domain+'.npy')
	num_domain_1_images = domain_1_reps.shape[0]
	num_domain_2_images = domain_2_reps.shape[0]
	rep_dim = domain_1_reps.shape[1]
	if rep_dim != domain_2_reps.shape[1]:
		print('Something wrong with representations !!')
		sys.exit(1)
	return domain_1_reps, domain_2_reps, domain_1_labels, domain_2_labels, num_domain_1_images, num_domain_2_images, rep_dim
##### End data loader #####

##### Initialize S_pos_set and R_set #####
def gen_s_pos(domain_1_reps, domain_2_reps, domain_1_labels, domain_2_labels, num_domain_1_images, num_domain_2_images, rep_dim, dict_domain_2):
	domain_class_data_X = np.concatenate((domain_1_reps, domain_2_reps), axis=0)
	domain_class_data_Y_1 = np.zeros((num_domain_1_images,1), dtype='float')
	domain_class_data_Y_2 = np.ones((num_domain_2_images,1), dtype='float')
	domain_class_data_Y = np.concatenate((domain_class_data_Y_1, domain_class_data_Y_2), axis=0).flatten()

	domain_class_scalar = preprocessing.StandardScaler().fit(domain_class_data_X)
	X_scaled_domain_class = domain_class_scalar.transform(domain_class_data_X)
	domain_classifier = svm.LinearSVC()
	domain_classifier.fit(X_scaled_domain_class, domain_class_data_Y)
	
	domain_class_2 = preprocessing.StandardScaler().fit(domain_2_reps)
	X_scaled_domain_2 = domain_class_2.transform(domain_2_reps)
	sample_distances = abs(domain_classifier.decision_function(X_scaled_domain_2))
	
	class_dist_dict = {}
	min_class_idx = int(min(domain_2_labels))
	max_class_idx = int(max(domain_2_labels))
	for given_class in range(min_class_idx, max_class_idx):
		sample_class_idxs = np.where(domain_2_labels == given_class)
		if given_class not in class_dist_dict.keys():
			class_dist_dict[given_class] = []
		for given_sample in sample_class_idxs[0]:
			given_sample_distance = sample_distances[given_sample]
			class_dist_dict[given_class].append((given_sample, given_sample_distance))
	
	reward_set = {}
	for given_class in class_dist_dict.keys():
		if given_class not in reward_set.keys():
			reward_set[given_class] = []
		given_class_list = sorted(class_dist_dict[given_class], key=lambda x:x[1])
		for given_sample in given_class_list[:num_reward_samples]:
			reward_set[given_class].append(given_sample[0])
			dict_domain_2[given_sample[0]] = int(1)
	s_pos = []
	sample_distances_pairs = []
	for given_sample in range(0, len(sample_distances)):
		sample_distances_pairs.append((given_sample, sample_distances[given_sample]))

	sorted_sample_dist = sorted(sample_distances_pairs, key=lambda x:x[1])
	for given_sample in sorted_sample_dist[len(sorted_sample_dist)-num_s_pos_samples:]:
		s_pos.append(given_sample[0])
		dict_domain_2[given_sample[0]] = int(1)
	return s_pos, reward_set, dict_domain_2

##### End Initialization #####

##### Train n-way classifier #####
def train_SVM(s_pos, domain_2_labels, domain_2_reps, rep_dim, reward_set, num_reward_set):
	num_samples = len(s_pos) + len(reward_set.keys())*num_reward_set
	X = np.zeros((num_samples, rep_dim), dtype='float')
	Y = np.zeros((num_samples, 1), dtype='float')
	i = 0
	for given_class in reward_set.keys():
		for given_class_sample in reward_set[given_class]:
			X[i,:] = domain_2_reps[given_class_sample,:]
			Y[i,:] = given_class
			i += 1
	for idx in range(0, len(s_pos)):
		given_sample = s_pos[idx]
		X[i,:] = domain_2_reps[given_sample,:]
		Y[i] = domain_2_labels[given_sample]
		i += 1
	scaler = preprocessing.StandardScaler().fit(X)
        X_scaled = scaler.transform(X)
        given_SVM = svm.LinearSVC(multi_class='ovr')
        given_SVM.fit(X_scaled, Y)
	return given_SVM

def test_check_accu(domain_2_reps, domain_2_labels, given_SVM, rep_dim):
        num_samples = domain_2_reps.shape[0]
        X = np.zeros((num_samples, rep_dim), dtype='float')
        Y = np.zeros((num_samples, 1), dtype='float')
        idx = 0
        for given_sample in range(0, num_samples):
        	X[idx,:] = domain_2_reps[given_sample,:]
                Y[idx] = domain_2_labels[given_sample]
                idx += 1
        scaler = preprocessing.StandardScaler().fit(X)
        X_scaled = scaler.transform(X)
        YY_ = given_SVM.predict(X_scaled)
        Y = Y.flatten()
        accu = accuracy_score(Y, YY_)
        return accu

def check_accu(reward_set, domain_2_reps, given_SVM, rep_dim):
	num_samples = sum([len(reward_set[i]) for i in reward_set.keys()])
	X = np.zeros((num_samples, rep_dim), dtype='float')
	Y = np.zeros((num_samples, 1), dtype='float')
	idx = 0
	for given_class in reward_set.keys():
		list_class = reward_set[given_class]
		for given_sample in list_class:
			X[idx,:] = domain_2_reps[given_sample,:]
			Y[idx] = given_class
			idx += 1
	scaler = preprocessing.StandardScaler().fit(X)
	X_scaled = scaler.transform(X)
	YY_ = given_SVM.predict(X_scaled)
	Y = Y.flatten()
	accu = accuracy_score(Y, YY_)
	return accu

##### End Train n-way classifier #####

##### Unlabeled predictions #####
def get_unlabelled_predictions(domain_1_reps, domain_2_reps, domain_1_labels):
	X = domain_1_reps
	Y = domain_1_labels
	Z = domain_2_reps
	scaler = preprocessing.StandardScaler().fit(X)
	X_scaled = scaler.transform(X)
	SVM = svm.LinearSVC(multi_class='ovr')
	SVM.fit(X_scaled, Y)
	scaler = preprocessing.StandardScaler().fit(Z)
	Z_scaled = scaler.transform(Z)
	unsupervised_labels = SVM.predict(Z_scaled)
	return unsupervised_labels
##### End Unlabeled predictions #####

def softmax(w, t = 1.0):
	e = np.exp(np.array(w) / t)
	dist = e / np.sum(e)
	return dist

def gen_state_samples(SVM, sampled_idxs, domain_2_reps, rep_dim):
	num_samples = len(sampled_idxs)
	num_classes = 31
	hist_out = np.zeros((num_samples, num_classes), dtype='float')
	X = np.zeros((num_samples, rep_dim), dtype='float')
	for i in range(0, num_samples):
		given_sample_idx = sampled_idxs[i]
		X[i,:] = domain_2_reps[given_sample_idx,:]
	scaler = preprocessing.StandardScaler().fit(X)
	X_scaled = scaler.transform(X)
	hist_all = SVM.decision_function(X_scaled)
	svm_predictions = SVM.predict(X_scaled)
	pred_classes = list(set([int(i) for i in svm_predictions]))
	for i in range(0, len(sampled_idxs)):
		given_sample = sampled_idxs[i]
		given_rep = softmax(abs(hist_all[i]))
		given_hist = np.zeros((1, num_classes), dtype='float')
		for given_class in range(0, num_classes):
			if given_class not in pred_classes:
				given_hist[0,given_class] = 0
			else:
				class_idx = pred_classes.index(given_class)
				given_hist[0,given_class] = given_rep[class_idx]
		hist_out[i,:] = given_hist
	return hist_out

def gen_state_pos(SVM, s_pos, domain_2_reps, rep_dim, num_hist=10):
	num_samples = len(s_pos)
	num_classes = 31
	hist_out = np.zeros((num_classes, num_hist), dtype='float')
	X = np.zeros((num_samples, rep_dim), dtype='float')
	idx = 0
	for given_sample in s_pos:
		X[idx,:] = domain_2_reps[given_sample,:]
		idx += 1
	scaler = preprocessing.StandardScaler().fit(X)
	X_scaled = scaler.transform(X)
	hist_all = SVM.decision_function(X_scaled)
	svm_predictions = SVM.predict(X_scaled)
	pred_classes = list(set([int(i) for i in svm_predictions]))
	for given_sample_idx in range(0, len(s_pos)):
		given_sample = s_pos[given_sample_idx]
		given_rep = softmax(abs(hist_all[given_sample_idx]))
		given_sample_class = int(svm_predictions[given_sample_idx])
		class_idx = pred_classes.index(given_sample_class)
		given_val = given_rep[class_idx]
		hist_div = float(1)/float(num_hist)
		given_hist = int(float(given_val)/float(hist_div))
		hist_out[given_sample_class][given_hist] += 1

	for given_class in range(0, num_classes):
		hist_out[given_class,:] = softmax(hist_out[given_class,:])

	return hist_out

def get_final_state_rep(h_pos, h_cand):
	h_pos = h_pos.flatten()
	h_cand = h_cand.flatten()
	h_final = np.concatenate((h_cand, h_pos), axis=0)
	state = np.zeros((1, h_final.shape[0]),dtype='float')
	state[0,:] = h_final
	return state
def print_state(h_pos, h_cand):
        h_pos = h_pos.flatten()
        h_cand = h_cand.flatten()
	for i in range(0, h_pos.shape[0]):
		print(str(h_pos[i]))
	print('\n\n')
	for i in range(0, h_cand.shape[0]):
        	print(str(h_cand[i]))
	sys.exit(1)
def init_dict_domain_2(domain_2_reps, domain_2_labels):
	dict_domain_2 = {}
	for i in range(0, domain_2_reps.shape[0]): dict_domain_2[i] = int(0)
	return dict_domain_2	

def sample_images(domain_2_reps, domain_2_labels, dict_domain_2, rep_dim, sample_num=100):
	available_samples = [i for i in dict_domain_2.keys() if dict_domain_2[i] == 0]
	sampled_idxs = np.random.choice(available_samples, size=sample_num, replace=False)
	return sampled_idxs

def check_reset(dict_domain_2, sample_num):
	available_samples = [i for i in dict_domain_2.keys() if dict_domain_2[i] == 0]
	if len(available_samples) < sample_num+1: return True
	else: return False

if __name__ == '__main__':

	source_domain = 'amazon'
	target_domain = 'webcam'
	num_s_pos_samples = 100
	num_reward_samples = 3
	max_iters = 20000
	sample_num = 20
	max_explore_iter = 2000
	num_hist = 10
	num_classes = 31
	data_dir = '/home/yash/Project/Amazon-finetune-features/'
	update_point = 10
	model_path = './a_to_w/model_best.h5'

	best_acu = float(0)
       	domain_1_reps, domain_2_reps, domain_1_labels, test_domain_2_labels, num_domain_1_images, num_domain_2_images, rep_dim = data_loader(source_domain, target_domain, num_s_pos_samples, num_reward_samples, data_dir)
        dict_domain_2 = init_dict_domain_2(domain_2_reps, test_domain_2_labels)
	s_pos, reward_set, dict_domain_2 = gen_s_pos(domain_1_reps, domain_2_reps, domain_1_labels, test_domain_2_labels, num_domain_1_images, num_domain_2_images, rep_dim, dict_domain_2)
	domain_2_labels = get_unlabelled_predictions(domain_1_reps, domain_2_reps, domain_1_labels)
	sampled_idxs = sample_images(domain_2_reps, domain_2_labels, dict_domain_2, rep_dim, sample_num)
	num_actions = len(sampled_idxs) + 1
	state_size = len(sampled_idxs)*num_classes + num_classes*num_hist
	q_agent = QNetwork(num_actions, state_size, model_path)
	given_SVM = train_SVM(s_pos, domain_2_labels, domain_2_reps, rep_dim, reward_set, num_reward_samples)
        accu = test_check_accu(domain_2_reps, test_domain_2_labels, given_SVM, rep_dim)
	print('Acu at 0: ' + str(accu))
        h_pos = gen_state_pos(given_SVM, s_pos, domain_2_reps, rep_dim)
        h_cand = gen_state_samples(given_SVM, sampled_idxs, domain_2_reps, rep_dim)
        state = get_final_state_rep(h_pos, h_cand)
        action = q_agent.get_action(state)
	best_acu = 0
        if action <= sample_num-1:
         	sample_id = sampled_idxs[action]
                s_pos.append(sample_id)
                dict_domain_2[sample_id] = 1
	for given_iter in range(1, max_iters):
		sampled_idxs = sample_images(domain_2_reps, domain_2_labels, dict_domain_2, rep_dim, sample_num)
		given_SVM = train_SVM(s_pos, domain_2_labels, domain_2_reps, rep_dim, reward_set, num_reward_samples)
		h_pos = gen_state_pos(given_SVM, s_pos, domain_2_reps, rep_dim)
		h_cand = gen_state_samples(given_SVM, sampled_idxs, domain_2_reps, rep_dim)
		state = get_final_state_rep(h_pos, h_cand)
		action = q_agent.get_action(state)
		if action <= sample_num-1:
			sample_id = sampled_idxs[action]
			s_pos.append(sample_id)
			dict_domain_2[sample_id] = 1
		else: print('Do nothing action taken')
		given_accu = test_check_accu(domain_2_reps, test_domain_2_labels, given_SVM, rep_dim)
		if given_accu >= best_acu:
			best_acu = given_accu
			print('Best Acu: ' + str(best_acu))
		print((str(given_accu) +'\t' + str(len(s_pos))))
                check_flag = check_reset(dict_domain_2, sample_num)
                if check_flag == True:
			break
	print(best_acu)
