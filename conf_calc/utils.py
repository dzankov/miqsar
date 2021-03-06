import sys
sys.path.append('/home/zankov/dev/miqsar')

import os
import torch
import random

import numpy as np
import pandas as pd

from miqsar.estimators.neural_nets.base_nets import BaseClassifier
from miqsar.estimators.neural_nets.mlp_nets import MIWrapperMLPClassifier, MIWrapperMLPRegressor
from miqsar.estimators.neural_nets.mlp_nets import miWrapperMLPClassifier, miWrapperMLPRegressor
from miqsar.estimators.neural_nets.attention_nets import AttentionNetClassifier, AttentionNetRegressor, \
    TempAttentionNetRegressor
from miqsar.estimators.neural_nets.attention_nets import GatedAttentionNetClassifier, GatedAttentionNetRegressor
from miqsar.estimators.neural_nets.mi_nets import MINetClassifier, MINetRegressor
from miqsar.estimators.neural_nets.mi_nets import miNetClassifier, miNetRegressor
from miqsar.estimators.neural_nets.utils import set_seed
from sklearn.metrics import confusion_matrix
from sklearn.preprocessing import MinMaxScaler
from collections import defaultdict
from sklearn.metrics import (r2_score, mean_squared_error, accuracy_score, balanced_accuracy_score,
                             average_precision_score,
                             brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score)

import os
import pandas as pd
from collections import defaultdict
from rdkit import Chem
from rdkit.Chem.Scaffolds.MurckoScaffold import MakeScaffoldGeneric
from sklearn.model_selection import train_test_split
from rdkit.Chem.Descriptors import ExactMolWt


class DataReader:
    def __init__(self, dsc_dir, dataset):
        self.data = {'dsc': dict(), 'labels': dict(), 'idx': dict()}
        self.dataset = dataset
        file = os.path.join(dsc_dir, dataset, '2DDescrRDKit_{}_0.csv'.format(self.dataset))
        self.mol_id = self.get_mol_id(file)
        _, self.data['labels'], self.data['idx'] = self.load_data(file, self.mol_id)

        pass

    def get_mol_id(self, fname):
        data = pd.read_csv(fname, index_col='mol_id')
        data.index = [i.upper() for i in data.index]
        data = data.sort_index()
        return data.index

    def load_data(self, fname, mol_id):
        data = pd.read_csv(fname, index_col='mol_id')
        data.index = [i.upper() for i in data.index]
        data = data.sort_index()

        # train
        idx = []
        bags = []
        labels = []
        for i in mol_id:
            if i in data.index.unique():
                bag = data.loc[i:i].drop(['mol_title', 'act'], axis=1).values
                label = float(data.loc[i:i]['act'].unique()[0])

                bags.append(bag)
                labels.append(label)
                idx.append(i)
            else:
                bags.append(bag)
                labels.append(label)
                idx.append(i)

        bags = np.array(bags)
        labels = np.array(labels)

        return bags, labels, idx

    def read_2d(self, dsc_dir):
        f1 = os.path.join(dsc_dir, self.dataset, '2DDescrRDKit_{}_0.csv'.format(self.dataset))
        f2 = os.path.join(dsc_dir, self.dataset, 'MorganFprRDKit_{}_0.csv'.format(self.dataset))
        f3 = os.path.join(dsc_dir, self.dataset, 'PhFprRDKit_{}_0.csv'.format(self.dataset))

        self.data['dsc']['2d'] = {'rdkit': self.load_data(f1, self.mol_id)[0],
                                  'morgan': self.load_data(f2, self.mol_id)[0],
                                  'phf': self.load_data(f3, self.mol_id)[0]}

        return self.data

    def read_3d(self, dsc_dir, n_conf):
        tmp = {}
        fname = os.path.join(dsc_dir, self.dataset, 'PhFprPmapper_conf-{}_{}.csv'.format(self.dataset, n_conf))
        tmp[n_conf] = self.load_data(fname, self.mol_id)[0]
        self.data['dsc']['3d_pmapper'] = tmp

        # tmp = {}
        # fname = os.path.join(dsc_dir, self.dataset, '3DDescrRDKit_conf-{}_{}.csv'.format(self.dataset, n_conf))
        # tmp[n_conf] = self.load_data(fname, self.mol_id)[0]
        # self.data['dsc']['3d_rdkit'] = tmp

        return self.data

    def read_2d_3d(self, dsc_dir, n_conf):
        data_2d = self.read_2d(dsc_dir)
        data_3d = self.read_3d(dsc_dir, n_conf)

        dsc_2d = data_2d['dsc']['2d']['morgan']
        dsc_3d = data_3d['dsc']['3d'][n_conf]

        new_3d = []
        for n, (vec_2d, vec_3d) in enumerate(zip(dsc_2d, dsc_3d)):
            if n_conf == 1:
                new_3d.append(np.concatenate([vec_2d, vec_3d], axis=1))
            else:
                new_3d.append(np.concatenate([np.tile(vec_2d, (vec_3d.shape[0], 1)), vec_3d], axis=1))

        self.data['dsc']['3d'][n_conf] = np.array(new_3d)

        return self.data


def scale_data(X_train, X_test):
    scaler = MinMaxScaler()
    scaler.fit(np.vstack(X_train))
    X_train_scaled = X_train.copy()
    X_test_scaled = X_test.copy()
    for i, bag in enumerate(X_train):
        X_train_scaled[i] = scaler.transform(bag)
    for i, bag in enumerate(X_test):
        X_test_scaled[i] = scaler.transform(bag)
    return X_train_scaled, X_test_scaled


def regression_metrics(y_true, y_pred):
    r2 = r2_score(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred) ** 0.5
    return {'r2_score': r2, 'rmse': rmse}


def classification_metrics(y_true, y_pred, threshold=0.5):
    thresholded_predictions = [1 if i.item() > threshold else 0 for i in y_pred]

    tn, fp, fn, tp = confusion_matrix(y_true, thresholded_predictions).ravel()

    accuracy = accuracy_score(y_true, thresholded_predictions)
    balanced_accuracy = balanced_accuracy_score(y_true, thresholded_predictions)
    average_precision = average_precision_score(y_true, thresholded_predictions)
    brier_score = brier_score_loss(y_true, thresholded_predictions)
    f1 = f1_score(y_true, thresholded_predictions)
    precision = precision_score(y_true, thresholded_predictions)
    recall = recall_score(y_true, thresholded_predictions)
    roc_auc = roc_auc_score(y_true, y_pred)

    return {'accuracy': accuracy, 'balanced_accuracy': balanced_accuracy, 'average_precision': average_precision,
            'brier_score': brier_score, 'f1': f1, 'precision': precision, 'recall': recall, 'roc_auc': roc_auc,
            'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp}


class ModelBuilder:

    def __init__(self, tresh=6.5, init_cuda=False, local_dir='./'):
        self.tresh = tresh
        self.init_cuda = init_cuda
        self.local_dir = local_dir

        self.n_epoch = 500
        self.batch_size = 99999
        self.lr = 0.001
        self.seed = 42

    def tune_nets(self, x_train, x_val, y_train, y_val):
        ndim = (x_train[0].shape[-1], 256, 128, 64)
        det_ndim = (64,)
        set_seed(self.seed)

        # weight_decay
        weight_decay_opt = defaultdict(list)
        for weight_decay in [0, 0.1, 0.01]:
            for net in [AttentionNetRegressor(ndim=ndim, det_ndim=det_ndim, init_cuda=self.init_cuda),
                        MINetRegressor(ndim=ndim, pool='mean', init_cuda=self.init_cuda),
                        miWrapperMLPRegressor(ndim=ndim, pool='mean', init_cuda=self.init_cuda)
                        ]:

                if 'Classifier' in net.__class__.__name__:
                    labels_train = np.where(y_train > self.tresh, 1, 0)
                    labels_val = np.where(y_val > self.tresh, 1, 0)

                    net.fit(x_train, labels_train, n_epoch=self.n_epoch, batch_size=self.batch_size,
                            weight_decay=weight_decay, lr=self.lr)

                    val_scores = classification_metrics(labels_val, net.predict(x_val))
                    weight_decay_opt[net.__class__.__name__].append((weight_decay, val_scores['balanced_accuracy']))
                else:
                    net.fit(x_train, y_train, n_epoch=self.n_epoch, batch_size=self.batch_size,
                            weight_decay=weight_decay, lr=self.lr)
                    val_scores = regression_metrics(y_val, net.predict(x_val))
                    weight_decay_opt[net.__class__.__name__].append((weight_decay, val_scores['r2_score']))
        #
        hopt = pd.DataFrame()
        for model in weight_decay_opt:
            hopt['WD'] = [i[0] for i in weight_decay_opt[model]]
            hopt[model] = [i[1] for i in weight_decay_opt[model]]
        hopt.to_csv(os.path.join(self.local_dir, 'weight_decay_opt.csv'))
        #
        weight_decay_opt = {k: max(v, key=lambda x: x[1])[0] for k, v in weight_decay_opt.items()}

        # dropout
        dropout_opt = defaultdict(list)
        for dropout in [0, 0.2, 0.5, 0.9, 0.95]:
            for net in [AttentionNetRegressor(ndim=ndim, det_ndim=det_ndim, init_cuda=self.init_cuda)]:

                if 'Classifier' in net.__class__.__name__:
                    labels_train = np.where(y_train > self.tresh, 1, 0)
                    labels_val = np.where(y_val > self.tresh, 1, 0)

                    net.fit(x_train, labels_train, n_epoch=self.n_epoch, batch_size=self.batch_size,
                        weight_decay=weight_decay_opt[net.__class__.__name__], dropout=dropout, lr=self.lr)

                    val_scores = classification_metrics(labels_val, net.predict(x_val))
                    dropout_opt[net.__class__.__name__].append((dropout, val_scores['balanced_accuracy']))
                else:
                    net.fit(x_train, y_train, n_epoch=self.n_epoch, batch_size=self.batch_size,
                            weight_decay=weight_decay_opt[net.__class__.__name__], dropout=dropout, lr=self.lr)
                    val_scores = regression_metrics(y_val, net.predict(x_val))
                    dropout_opt[net.__class__.__name__].append((dropout, val_scores['r2_score']))
        #
        hopt = pd.DataFrame()
        for model in dropout_opt:
            hopt['DP'] = [i[0] for i in dropout_opt[model]]
            hopt[model] = [i[1] for i in dropout_opt[model]]
        hopt.to_csv(os.path.join(self.local_dir, 'dropout_opt_opt.csv'))
        #
        dropout_opt = {k: max(v, key=lambda x: x[1])[0] for k, v in dropout_opt.items()}

        #
        nets_default = [[k, 0, 0] for k in weight_decay_opt]
        nets_tuned = [['{}Tuned'.format(k), weight_decay_opt[k], dropout_opt.get(k, 0)] for k in weight_decay_opt]

        return nets_default, nets_tuned

    def train_nets(self, nets_to_train, x_train, x_val, x_test, y_train, y_val, y_test, idx_val, idx_test, mode='3d'):

        ndim = (x_train[0].shape[-1], 256, 128, 64)
        det_ndim = (64,)
        set_seed(self.seed)

        estimators = [AttentionNetRegressor(ndim=ndim, det_ndim=det_ndim, init_cuda=self.init_cuda),
                      MINetRegressor(ndim=ndim, pool='mean', init_cuda=self.init_cuda),
                      miWrapperMLPRegressor(ndim=ndim, pool='mean', init_cuda=self.init_cuda)]

        results = pd.DataFrame()
        for net, (model_name, weight_decay, dropout) in zip(estimators, nets_to_train):
            if mode == '3d':
                pass
            elif not (mode == '2d' and isinstance(net, (MINetClassifier, MINetRegressor))):
                continue

            #
            model_dir = os.path.join(self.local_dir, model_name)
            os.mkdir(model_dir)

            # fit_predict
            if 'Classifier' in net.__class__.__name__:
                labels_train = np.where(y_train > self.tresh, 1, 0)
                labels_val = np.where(y_val > self.tresh, 1, 0)
                labels_test = np.where(y_test > self.tresh, 1, 0)

                net.fit(x_train, labels_train, n_epoch=self.n_epoch, batch_size=self.batch_size,
                        weight_decay=weight_decay, dropout=dropout, lr=self.lr)

                train_scores = classification_metrics(labels_train, net.predict(x_train))
                val_scores = classification_metrics(labels_val, net.predict(x_val))
                test_scores = classification_metrics(labels_test, net.predict(x_test))
            else:

                net.fit(x_train, y_train, n_epoch=self.n_epoch, batch_size=self.batch_size,
                        weight_decay=weight_decay, dropout=dropout, lr=self.lr)

                train_scores = regression_metrics(y_train, net.predict(x_train))
                val_scores = regression_metrics(y_val, net.predict(x_val))
                test_scores = regression_metrics(y_test, net.predict(x_test))
            #
            train_scores = {**{'SIZE': len(y_train)}, **{'MODEL': model_name, 'SET': 'TRAIN'}, **train_scores}
            val_scores = {**{'SIZE': len(y_val)}, **{'MODEL': model_name, 'SET': 'VAL'}, **val_scores}
            test_scores = {**{'SIZE': len(y_test)}, **{'MODEL': model_name, 'SET': 'TEST'}, **test_scores}

            # predictions
            predictions = pd.DataFrame({'TEST_ID': idx_test,
                                        'TEST_TRUE': y_test,
                                        'TEST_PRED': net.predict(x_test).flatten()})
            predictions.to_csv(os.path.join(model_dir, 'predictions.csv'))

            # results
            results = results.append([train_scores, val_scores, test_scores])

            # save model
            torch.save(net, os.path.join(model_dir, 'model.sav'))

        csv_file = os.path.join(self.local_dir, 'results.csv')
        if os.path.exists(csv_file):
            results.to_csv(csv_file, index=False, mode='a', header=False)
        else:
            results.to_csv(csv_file, index=False)

        return self


def ti_train_test_split_scaffold(datasets_path, chembl, bags, labels, idx, random_state=45):
    class Molecule:
        def __init__(self, smiles=None, scaffold=None, idx=None):
            self.smiles = smiles
            self.scaffold = scaffold
            self.idx = idx
            return

    # datasets = '/home/zankov/dev/miqsar/datasets/tautomers/'
    data = pd.read_csv(os.path.join(datasets_path, chembl), header=None)

    mols = []
    for smi, idxes in zip(data[0].to_list(), data[1].to_list()):
        if ExactMolWt(Chem.MolFromSmiles(smi)) > 700:
            continue
        try:
            mols.append(Molecule(smiles=smi, scaffold=Chem.MolToSmiles(MakeScaffoldGeneric(Chem.MolFromSmiles(smi))), idx=idxes))
        except:
            continue

    #
    res = defaultdict(list)
    for mol in mols:
        res[mol.scaffold].append(mol.idx)
    #
    test_size = int(len(data) * 0.2)

    test_idx = []
    train_idx = []
    res_sorted = sorted([(len(v), v) for k, v in res.items()], key=lambda x: x[0])

    for i in res_sorted:
        if len(test_idx) < test_size:
            test_idx.extend(i[1])
        else:
            train_idx.extend(i[1])

    #
    bags_train = []
    labels_train = []
    bags_test = []
    labels_test = []
    idx_train = []
    idx_test = []
    for bag, label, i in zip(bags, labels, idx):
        if i in train_idx:
            bags_train.append(bag)
            labels_train.append(label)
            idx_train.append(i)
        else:
            bags_test.append(bag)
            labels_test.append(label)
            idx_test.append(i)

    return bags_train, bags_test, labels_train, labels_test, idx_train, idx_test


def pg_train_test_split_scaffold(datasets_path, chembl, bags, labels, idx, random_state=45):
    class Molecule:
        def __init__(self, smiles=None, scaffold=None, idx=None):
            self.smiles = smiles
            self.scaffold = scaffold
            self.idx = idx
            return

    # datasets = '/home/zankov/dev/miqsar/datasets/tautomers/'
    data = pd.read_csv(os.path.join(datasets_path, chembl), header=None)

    mols = []
    for smi, idxes in zip(data[0].to_list(), data[1].to_list()):
        if ExactMolWt(Chem.MolFromSmiles(smi)) > 700:
            continue
        try:
            mols.append(
                Molecule(smiles=smi, scaffold=Chem.MolToSmiles(MakeScaffoldGeneric(Chem.MolFromSmiles(smi))), idx=idxes))
        except:
            continue

    #
    res = defaultdict(list)
    for mol in mols:
        res[mol.scaffold].append(mol.idx)
    #
    test_size = int(len(data) * 0.2)

    res = [(len(v), v) for k, v in res.items()]
    random.seed(random_state)
    random.shuffle(res)

    test_idx = []
    train_idx = []
    for i in res:
        if len(test_idx) < test_size:
            test_idx.extend(i[1])
        else:
            train_idx.extend(i[1])

    #
    bags_train = []
    labels_train = []
    bags_test = []
    labels_test = []
    idx_train = []
    idx_test = []
    for bag, label, i in zip(bags, labels, idx):
        if i in train_idx:
            bags_train.append(bag)
            labels_train.append(label)
            idx_train.append(i)
        else:
            bags_test.append(bag)
            labels_test.append(label)
            idx_test.append(i)

    return bags_train, bags_test, labels_train, labels_test, idx_train, idx_test