import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import average_precision_score, precision_recall_curve
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.metrics import roc_auc_score, roc_curve, auc
from sklearn.model_selection import GridSearchCV

from healthcareai.common.feature_importances import write_feature_importances
from healthcareai.common.output_utilities import save_object_as_pickle, load_pickle_file


def clfreport(modeltype,
              debug,
              devcheck,
              algo,
              X_train,
              y_train,
              X_test,
              y_test=None,
              param=None,
              cores=4,
              tune=False,
              use_saved_model=False,
              col_list=None):
    """
    Given a model type, algorithm and test data, do/return/save/side effect the following in no particular order:
    - [x] runs grid search
    - [ ] save/load a pickled model
    - [ ] print out debug messages
    - [x] train the classifier
    - [ ] print out grid params
    - [ ] calculate metrics
    - [ ] feature importances
    - [ ] logging
    - [ ] production predictions from pickle file
    - do some numpy manipulation
        - lines ~50?
    - possible returns:
        - a single prediction
        - a prediction and an roc_auc score
        - spits out feature importances (if they exist)
        - saves a pickled model

    Note this serves at least 3 uses
    """

    # Initialize conditional vars that depend on ifelse to avoid PC warning
    y_pred_class = None
    y_pred = None
    clf = algo

    # compare algorithms
    if devcheck == 'yesdev':
        if tune:
            # Set up grid search
            clf = GridSearchCV(algo, param, cv=5, scoring='roc_auc', n_jobs=cores)

        if debug:
            print('\nclf object right before fitting main model:')
            print(clf)

        print('\n', algo)

        if modeltype == 'classification':
            y_pred = np.squeeze(clf.fit(X_train, y_train).predict_proba(X_test)[:, 1])
            #y_pred_class = clf.fit(X_train, y_train).predict(X_test)

            roc_auc = roc_auc_score(y_test, y_pred)
            precision, recall, thresholds = precision_recall_curve(y_test, y_pred)
            pr_auc = auc(recall, precision)

            print_classification_metrics(pr_auc, roc_auc)
        elif modeltype == 'regression':
            y_pred = clf.fit(X_train, y_train).predict(X_test)

            print_regression_metrics(y_pred, y_pred_class, y_test)

        if hasattr(clf, 'best_params_') and tune:
            print("Best hyper-parameters found after tuning:")
            print(clf.best_params_)
        else:
            print("No hyper-parameter tuning was done.")


        # TODO: refactor this logic to be simpler
        # Return without printing variable importance for linear case
        if (not hasattr(clf, 'feature_importances_')) and (not
            hasattr(clf, 'best_estimator_')):

            return y_pred, roc_auc

        # Print variable importance if rf and not tuning
        elif hasattr(clf, 'feature_importances_'):
            write_feature_importances(clf.feature_importances_, col_list)

            return y_pred, roc_auc, clf

        # Print variable importance if rf and tuning
        elif hasattr(clf.best_estimator_, 'feature_importances_'):
            write_feature_importances(clf.best_estimator_.feature_importances_, col_list)

            return y_pred, roc_auc, clf

    elif devcheck == 'notdev':
        if use_saved_model is True:
            clf = load_pickle_file('probability.pkl')
        else:
            if debug:
                print('\nclf object right before fitting main model:')

            clf.fit(X_train, y_train)
            save_object_as_pickle('probability.pkl', clf)

        if modeltype == 'classification':
            y_pred = np.squeeze(clf.predict_proba(X_test)[:, 1])
        elif modeltype == 'regression':
            y_pred = clf.predict(X_test)

    return y_pred


def print_regression_metrics(y_pred, y_pred_class, y_test):
    print('##########################################################')
    print('Model accuracy:')
    print('\nRMSE error:', math.sqrt(mean_squared_error(y_test, y_pred_class)))
    print('\nMean absolute error:', mean_absolute_error(y_test, y_pred), '\n')
    print('##########################################################')


def print_classification_metrics(pr_auc, roc_auc):
    print('\nMetrics:')
    print('AU_ROC ScoreX:', roc_auc)
    print('\nAU_PR Score:', pr_auc)


def find_top_three_factors(debug,
                           X_train,
                           y_train,
                           X_test,
                           model_type,
                           use_saved_model):

    # Initialize conditional vars that depend on ifelse to avoid PC warnng
    clf = None

    if model_type == 'classification':
        clf = LogisticRegression()
    elif model_type == 'regression':
        clf = LinearRegression()

    if use_saved_model is True:
        clf = load_pickle_file('factorlogit.pkl')
    elif use_saved_model is False:
        if debug:
            print('\nclf object right before fitting factor ranking model')
            print(clf)

        if model_type == 'classification':
            clf.fit(X_train, y_train).predict_proba(X_test)
        elif model_type == 'regression':
            clf.fit(X_train, y_train).predict(X_test)
            save_object_as_pickle('factorlogit.pkl', clf)

    if debug:
        print('\nCoeffs right before multiplic. to determine top 3 factors')
        print(clf.coef_)
        print('\nX_test right before this multiplication')
        print(X_test.loc[:3, :])

    # Populate X_test array of ordered col importance;
    # Start by multiplying X_test vals by coeffs
    res = X_test.values * clf.coef_

    if debug:
        print('\nResult of coef * Xtest row by row multiplication')
        for i in range(0, 3):
            print(res[i, :])

    col_list = X_test.columns.values

    first_fact = []
    second_fact = []
    third_fact = []

    if debug:
        print('\nSorting column importance rankings for each row in X_test...')

    # TODO: switch 2-d lists to numpy array
    # (although would always convert back to list for ceODBC
    for i in range(0, len(res[:, 1])):
        list_of_indexrankings = np.array((-res[i]).argsort().ravel())
        first_fact.append(col_list[list_of_indexrankings[0]])
        second_fact.append(col_list[list_of_indexrankings[1]])
        third_fact.append(col_list[list_of_indexrankings[2]])

    if debug:
        print('\nTop three factors for top five rows:')  # pretty-print w/ df
        print(pd.DataFrame({'first': first_fact[:3],
                            'second': second_fact[:3],
                            'third': third_fact[:3]}))

    return first_fact, second_fact, third_fact



def GenerateAUC(predictions, labels, aucType='SS', plotFlg=False, allCutoffsFlg=False):
    # TODO refactor this
    """
    This function creates an ROC or PR curve and calculates the area under it.

    Parameters
    ----------
    predictions (list) : predictions coming from an ML algorithm of length n.
    labels (list) : true label values corresponding to the predictions. Also length n.
    aucType (str) : either 'SS' for ROC curve or 'PR' for precision recall curve. Defaults to 'SS'
    plotFlg (bol) : True will return plots. Defaults to False.
    allCutoffsFlg (bol) : True will return plots. Defaults to False.

    Returns
    -------
    AUC (float) : either AU_ROC or AU_PR
    """
    # Error check for uneven length predictions and labels
    if len(predictions) != len(labels):
        raise Exception('Data vectors are not equal length!')

    # make AUC type upper case.
    aucType = aucType.upper()

    # check to see if AUC is SS or PR. If not, default to SS
    if aucType != 'SS' and aucType != 'PR':
        print('Drawing ROC curve with Sensitivity/Specificity')
        aucType = 'SS'

    # Compute ROC curve and ROC area
    if aucType == 'SS':
        fpr, tpr, thresh = roc_curve(labels, predictions)
        area = auc(fpr, tpr)
        print('Area under ROC curve (AUC): %0.2f' % area)
        # get ideal cutoffs for suggestions
        d = (fpr - 0)**2 + (tpr - 1)**2
        ind = np.where(d == np.min(d))
        bestTpr = tpr[ind]
        bestFpr = fpr[ind]
        cutoff = thresh[ind]
        print("Ideal cutoff is %0.2f, yielding TPR of %0.2f and FPR of %0.2f" % (cutoff, bestTpr, bestFpr))
        if allCutoffsFlg is True:
            print('%-7s %-6s %-5s' % ('Thresh', 'TPR', 'FPR'))
            for i in range(len(thresh)):
                print('%-7.2f %-6.2f %-6.2f' % (thresh[i], tpr[i], fpr[i]))

        # plot ROC curve
        if plotFlg is True:
            plt.figure()
            plt.plot(fpr, tpr, color='darkorange',
                     lw=2, label='ROC curve (area = %0.2f)' % area)
            plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel('False Positive Rate')
            plt.ylabel('True Positive Rate')
            plt.title('Receiver operating characteristic curve')
            plt.legend(loc="lower right")
            plt.show()
        return ({'AU_ROC': area,
                 'BestCutoff': cutoff[0],
                 'BestTpr': bestTpr[0],
                 'BestFpr': bestFpr[0]})
    # Compute PR curve and PR area
    else: # must be PR
        # Compute Precision-Recall and plot curve
        precision, recall, thresh = precision_recall_curve(labels, predictions)
        area = average_precision_score(labels, predictions)
        print('Area under PR curve (AU_PR): %0.2f' % area)
        # get ideal cutoffs for suggestions
        d = (precision - 1) ** 2 + (recall - 1) ** 2
        ind = np.where(d == np.min(d))
        bestPre = precision[ind]
        bestRec = recall[ind]
        cutoff = thresh[ind]
        print( "Ideal cutoff is %0.2f, yielding TPR of %0.2f and FPR of %0.2f"
               % (cutoff, bestPre, bestRec))
        if allCutoffsFlg is True:
            print('%-7s %-10s %-10s' % ('Thresh', 'Precision', 'Recall'))
            for i in range(len(thresh)):
                print('%5.2f %6.2f %10.2f' %(thresh[i],precision[i], recall[i]))

        # plot PR curve
        if plotFlg is True:
            # Plot Precision-Recall curve
            plt.figure()
            plt.plot(recall, precision, lw=2, color='darkred',
                     label='Precision-Recall curve' % area)
            plt.xlabel('Recall')
            plt.ylabel('Precision')
            plt.ylim([0.0, 1.05])
            plt.xlim([0.0, 1.0])
            plt.title('Precision-Recall AUC={0:0.2f}'.format(
                area))
            plt.legend(loc="lower right")
            plt.show()
        return({'AU_PR':area,
                'BestCutoff':cutoff[0],
                'BestPrecision':bestPre[0],
                'BestRecall':bestRec[0]})

if __name__ == "__main__":
    pass
