import pandas as pd
import numpy as np
import json
import sklearn
from sklearn.feature_extraction.text import CountVectorizer
from nltk import word_tokenize
from nltk.stem.porter import PorterStemmer
import string
import re
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import itertools
from CZ4034.settings import *

#Train the classifier
def get_classifier():

    train_json = pd.read_json(STATICFILES_DIRS[1]+"\\Data\\training.json", orient="columns")
    target = train_json["category"]

    #Convertto ti-idf document term matrix
    train_list = get_count_vect_train(train_json["content"])
    train_count_vect = train_list[0]
    train_vector = train_list[1]
    train_tfidf = tf_idf(train_vector)

    #Split training set and testing set
    X_train, X_test, y_train, y_test = train_test_split(train_tfidf, target, test_size=0.3, random_state=0)

    #Get classifier
    clf = LinearSVC().fit(X_train, y_train)
    return [train_count_vect, clf]

#Tokenize the text
def tokenize(text):

    #Create Stemmer
    stemmer = PorterStemmer()

    #Remove irrelevant character
    text = re.sub(r"http\S+", '', text)
    text = re.sub(r"[^a-zA-Z]", ' ', text)

    #Tokenization
    tokens = word_tokenize(text)
    tokens = [i for i in tokens if i not in string.punctuation]

    #Stemming
    stems = stem_tokens(tokens, stemmer)
    return stems

#Stemming Function
def stem_tokens(t,s):
    stemmed=[]
    for item in t:
        stemmed.append(s.stem(item))
    return stemmed

#Remove stop words and convert training data text into term-document martrix
def get_count_vect_train(content_list):

    count_vect = CountVectorizer(stop_words='english', tokenizer=tokenize)
    X_train_counts = count_vect.fit_transform(content_list)
    count_vect.vocabulary_.get(u'algorithm')
    return [count_vect, X_train_counts]

#Convert to tf-idf matrix
def tf_idf(vect_text):
    tf_trans = TfidfTransformer(use_idf=True).fit_transform(vect_text)
    return tf_trans

#Convert testing data text into term document matrix
def get_count_vect_test(content_list, count_vect):
    X_train_counts = count_vect.transform(content_list)
    return X_train_counts

#Predict tweet category
def predict(content_list, train_count_vect, clf):
    test_vector = get_count_vect_test(content_list,train_count_vect)
    test_tfidf = tf_idf(test_vector)
    pred = clf.predict(test_tfidf)
    return pred
