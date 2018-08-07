#!/usr/bin/python

import sys 
import pickle 
import pandas as pd
import numpy as np
sys.path.append("../tools/")

from feature_format import featureFormat, targetFeatureSplit 
from tester import dump_classifier_and_data

# ignore warnings
import warnings
warnings.filterwarnings("ignore")

#############################################################################
# Task 1: Select what features you'll use 
#############################################################################

features_list = ['poi', 'salary', 'deferral_payments', 'total_payments',
'loan_advances', 'bonus', 'restricted_stock_deferred', 'deferred_income', 
'total_stock_value', 'expenses', 'exercised_stock_options', 'other', 
'long_term_incentive', 'restricted_stock', 'director_fees', 'to_messages',
'from_poi_to_this_person', 'from_messages', 'from_this_person_to_poi', 
'shared_receipt_with_poi']

selected_features = ['poi', 'salary', 'total_payments', 'bonus', 
'total_stock_value', 'exercised_stock_options', 'long_term_incentive', 
'restricted_stock', 'to_messages', 'shared_receipt_with_poi']

# load the dictionary containing the dataset 
with open("final_project_dataset.pkl", "r") as data_file:     
	data_dict = pickle.load(data_file)

# create pandas df from dictionary and transpose axes for easier manipulation 
df = pd.DataFrame.from_dict(data_dict).transpose()

# replace string 'NaN' with nan value
df = df.replace('NaN', np.nan)

# drop email address column
df = df.drop('email_address', axis = 1)

# find missing values per row
empty_rows = df.isnull().sum(axis=1)
empty_rows.sort(ascending = False)

# drop LOCKHART for missing all values (except POI labeling)
df = df.drop(['LOCKHART EUGENE E'])

#############################################################################
# Task 2: Remove outliers
#############################################################################

# removing TOTAL and THE TRAVEL AGENCY IN THE PARK rows 
df = df.drop(['TOTAL','THE TRAVEL AGENCY IN THE PARK'])

# replace missing values with 0 
df = df.fillna(0)

# calculate the total payments
df['total_p'] = df[['bonus', 'deferral_payments', 'deferred_income', 
					'director_fees', 'expenses', 'loan_advances', 
                    'long_term_incentive', 'other', 'salary']].sum(axis = 1)

# calculate difference between own calculation and column total_payments
df['diff'] = df['total_p'] - df['total_payments']

# show names for who the calculated and supplied total payments are not equal
names = df.index[df['diff'] != 0].tolist()

# remove created columns from df
df = df.drop(['total_p', 'diff'], axis = 1)

# drop two employees (BELFER and BHATNAGAR) with incorrect values
df = df.drop(names)

# create new_df with the correct values from enron61702insiderpay.pdf
values = [[0, 0, 0, 0, 15456290, 137864, 29, 0, 1, 0, 0, 0, False, 2604490, 
		  -2604490, 0, 463, 523, 137864, 15456290], 
          [0, 0, -102500, 102500, 0, 3285, 0, 0, 0, 0, 0, 0, False, 44093, 
          -44093, 0, 0, 0, 3285, 0]]

new_df = pd.DataFrame(values, columns = list(df), 
	index = ['BHATNAGAR SANJAY', 'BELFER ROBERT'])

# append new_df to df 
df = df.append(new_df)

# sort index so the names are sorted alfabetically again
df = df.sort_index(axis = 0)

#############################################################################
# Task 3: Create new feature(s) 
#############################################################################

# create bonus to salary ratio
df['bonus_salary_ratio'] = df['bonus'] / df['salary']

# create bonus to total payments ratio
df['bonus_tp_ratio'] = df['bonus'] / df['total_payments']

# replace nan values with 0 
df = df.fillna(0)

# select features 
def select_features(list_features, new):
	features = list_features
	if new == True:
		features += ['bonus_tp_ratio','bonus_salary_ratio']
	return features 

features = select_features(selected_features, True)

# create dataframe for selected features
df = df.ix[:, features] 

# create new features list
new_features_list = list(df)

# store dictionary to my_dataset
my_dataset = df.to_dict('index')

# extract features and labels from dataset for testing  
data = featureFormat(my_dataset, new_features_list, sort_keys = True) 
labels, features = targetFeatureSplit(data)

#############################################################################
# Task 4: Try a variety of classifiers
#############################################################################

# import packages
import sklearn
from sklearn.feature_selection import SelectKBest
from sklearn.naive_bayes import GaussianNB 
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn import model_selection
from sklearn.model_selection import StratifiedShuffleSplit, GridSearchCV
from sklearn import cross_validation
from sklearn.cross_validation import train_test_split

# create scaler
scaler = StandardScaler()

# create feature selection method
select = SelectKBest()

# create different classifiers
dt = DecisionTreeClassifier()
gnb = GaussianNB()
knn = KNeighborsClassifier()

pipeline = Pipeline([('feature_selection', select)])

# create pipeline for gnb & dt
pipeline = Pipeline([('feature_selection', select), ('classifier', dt)])

# create pipeline for knn
#pipeline = Pipeline([('scaler', scaler), ('feature_selection', select), ('classifier', knn)])

# create parameters to explore in grid search
parameters = dict(
	feature_selection__k = range(2,10),
    # dt
    classifier__splitter = ['best', 'random'],
    classifier__criterion = ['entropy', 'gini'], 
    classifier__min_samples_split = [4,6],
    classifier__class_weight = ['balanced', None],
    classifier__min_samples_leaf = [12,15],
    classifier__random_state = [42]
    # knn
    #classifier__n_neighbors = [2,3,4,5],
    #classifier__weights = ['uniform', 'distance'],
   	#classifier__algorithm = ['auto', 'ball_tree', 'kd_tree', 'brute'],
    #classifier__p = [1,2,3]
    )

#############################################################################
# Task 5: Tune your classifier to achieve better than .3 p & r scores
#############################################################################

# import package
from sklearn.metrics import classification_report

# create training and test data 
features_train, features_test, labels_train, labels_test = \
train_test_split(features, labels, test_size = 0.3, random_state = 42)

# create stratified shuffle split 
sss = StratifiedShuffleSplit(n_splits=100, test_size = 0.3, random_state = 42)

# create grid search
gs = GridSearchCV(pipeline, param_grid = parameters, cv = sss, scoring = 'f1', n_jobs = 10)

# fit to total dataset due to size and imbalances
gs.fit(features,labels)

# find parameter values
gs.best_params_

# assign best estimator model to clf
clf = gs.best_estimator_
print 'Best model found by grid search:'
print clf
print '\n'

# create classification report
#predictions = gs.predict(features_test)
#names = ['non-POI', 'POI']
#report = classification_report(labels_test, predictions, target_names = names)
#print report

# find indices of the features that are selected
list_feat = clf.named_steps['feature_selection'].get_support(indices = True)
    
# get scores for features
scores = clf.named_steps['feature_selection'].scores_

# get importances for selected features
importances = clf.named_steps['classifier'].feature_importances_

# sort indices with highest importance first
indices = np.argsort(importances)[::-1]

# create list with names & scores of selected features
selected_features_list = ['poi']
scores_list = []
for i in list_feat:
	selected_features_list.append(new_features_list[i + 1])
	scores_list.append(scores[i])

print 'Feature Ranking: (importance - score)'
for i in indices:
	print "{} ({} - {})".format(
		selected_features_list[i+1],
		round(importances[i],3), 
		round(scores_list[i],3))

#############################################################################
# Task 6: Dump your classifier, dataset, and features_list
#############################################################################

dump_classifier_and_data(clf, my_dataset, new_features_list)
