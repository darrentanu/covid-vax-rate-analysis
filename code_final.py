'''
MISM 6212
FINAL PROJECT
Darren Tanuwidjaja, Jack Wilson, Minda Kone, Sara Simkovitz, Fatemeh Mohamedi

Predicting COVID-19 Vaccination Rates by County Across U.S.
'''

#%% IMPORT LIBRARIES
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from kneed import KneeLocator
from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split
from sklearn.decomposition import PCA
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import silhouette_score
from sklearn.linear_model import LinearRegression
from xgboost import cv
import xgboost as xgb 
from sklearn.model_selection import GridSearchCV
from sklearn import metrics
from sklearn.metrics import mean_squared_error
import numpy as np
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import KFold

#%% IMPORT COUNTY ELECTION DATA 

states = ['AL', 'AR', 'AZ', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
           'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME',
           'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM',
           'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX',
           'UT', 'VA', 'VT', 'WA', 'WI', 'WV', 'WY']

df = pd.read_csv('county_election_AK.csv')
df.drop(df.tail(1).index, axis=0, inplace=True)
df['state'] = 'AK'

dc = pd.read_csv('county_election_DC.csv')
dc = dc[dc['County']=='District of Columbia']
dc['state'] = 'DC'

df = df.append(dc)

for state in states:
    name = str('county_election_')+state+str('.csv')
    #print(name)
    working_df = pd.read_csv(name)
    working_df['state'] = state
    working_df.drop(working_df.tail(1).index, axis=0, inplace=True)
    df = df.append(working_df)

#%% COUNTY ELECTION DATA PREPROCESSING
# Combining improperly formatted plurality columns
df['Plurality'] = df['Plurality'].fillna(df['Plurality '])
df['Plurality'] = df['Plurality'].fillna(df['Pluraltiy '])
df['Plurality'] = df['Plurality'].fillna(df['Pluralty '])
df['Plurality'] = df['Plurality'].fillna(df['plurality '])

df['Plurality Count'] = df['Plurality Count'].fillna(df['Plurality count'])

# Dropping improperly formatted columns
columns = ['Plurality ', 'Pluraltiy ', 'Pluralty ', 'plurality ', 'Plurality count']
df = df.drop(columns=columns, axis=1)

# Dropping columns with too many NAs
df.isna().sum()
df = df.drop(columns=['Other Vote', 'Other'], axis=1)

# Rename columns for Rep, Dem, Independent
df.rename(columns = {'Rep.': 'Rep_Total_Vote',
                     'Dem.': 'Dem_Total_Vote',
                     'Independent.1': 'Independent_Total_Vote',
                     'Rep..1': 'Rep_Maj_Vote',
                     'Dem..1': 'Dem_Maj_Vote'}, inplace=True)
df.rename(columns=lambda x: x.lower().replace(' ','_'), inplace=True)

# Fixing data types
def numerify(number):
    x = (number.replace(',',''))
    return x

df['total_vote'] = df['total_vote'].apply(lambda x: numerify(x))
df['total_vote'] = df['total_vote'].astype('float64')

df['plurality_count'] = df['plurality_count'].apply(lambda x: numerify(x))
df['plurality_count'] = df['plurality_count'].astype('float64')

df['republican'] = df['republican'].apply(lambda x: numerify(x))
df['republican'] = df['republican'].astype('float64')

df['democratic'] = df['democratic'].apply(lambda x: numerify(x))
df['democratic'] = df['democratic'].astype('float64')

df['independent'] = df['independent'].apply(lambda x: numerify(x))
df['independent'] = df['independent'].astype('float64')

df = pd.get_dummies(df, columns=['plurality'])

df = df[df['county'] != 'NORFOLK']

df.sort_values(by=['state', 'county'], inplace=True)
df.reset_index(inplace=True, drop=True)

#%% WRITE CSV CLEANED COUNTY ELECTION DATA
df.to_csv("county_election_data_clean.csv", index= False)

#%% IMPORT COVID DATA
df_covid = pd.read_csv('county_vac_data.csv')

#%% COVID DATA PREPROCESSING

# Check NAs and duplicates
df_covid.isna().sum()
df_covid[df_covid.duplicated()]

# Drop URL column - not useful in analysis
df_covid.drop('url', axis=1, inplace=True)

# Drop Puerto Rico - no data in other datasets for this state
df_covid.set_index('state', inplace=True)
df_covid.drop('PR', axis=0, inplace=True)
df_covid.reset_index(inplace=True)


#%% IMPORT HEALTH DATA
df_health = pd.read_csv('analytic_data2021.csv')
health_columns = df_health.columns.to_list()

# Select predictors wanted from health data
indices = [3,4,33,69,74,84,94,104,129,139,172,182,192,197,217,232,275,306,346,
           366,396,401,406,416,507,542,583,630,635,640,645,650,655,665,670,680,685]
columns = [health_columns[i] for i in indices]

# Filter health data for selected columns
df_health = df_health[columns]
df_health.drop(df_health.head(2).index, axis=0, inplace=True)
df_health.reset_index(inplace=True, drop=True)

#%% HEALTH DATA PREPROCESSING

# Removing state total rows
df_health['countby_st'] = 1
for i in range(1, len(df_health)):
    if df_health['State Abbreviation'][i] == df_health['State Abbreviation'][i-1]:
        df_health['countby_st'][i] = df_health['countby_st'][i-1]+1
    else:
        pass

df_health.loc[df_health['countby_st'] == 1].shape
df_health = df_health[df_health['countby_st'] != 1]
df_health.drop('countby_st', axis=1, inplace=True)

df_health.sort_values(by=['State Abbreviation', 'Name'], inplace=True)
df_health.reset_index(inplace=True, drop=True)

# Convert incorrectly formatted data types
cols = ['Poor or fair health raw value',
       'Adult smoking raw value', 'Adult obesity raw value',
       'Physical inactivity raw value', 'Excessive drinking raw value',
       'Sexually transmitted infections raw value', 'Uninsured raw value',
       'Ratio of population to primary care physicians.',
       'Flu vaccinations raw value', 'High school completion raw value',
       'Unemployment raw value', 'Children in poverty raw value',
       'Income inequality raw value', 'Violent crime raw value',
       'Percentage of households with overcrowding',
       'Life expectancy raw value', 'Child mortality raw value',
       'Infant mortality raw value', 'Diabetes prevalence raw value',
       'HIV prevalence raw value', 'Food insecurity raw value',
       'Drug overdose deaths raw value', 'Median household income raw value',
       'Homicides raw value', 'Firearm fatalities raw value',
       'Population raw value', '% below 18 years of age raw value',
       '% 65 and older raw value', '% Non-Hispanic Black raw value',
       '% American Indian & Alaska Native raw value', '% Asian raw value',
       '% Hispanic raw value', '% Non-Hispanic White raw value',
       '% Females raw value', '% Rural raw value']

for col in cols:
    df_health[col] = df_health[col].astype('float64')

df_health.rename(columns = {'State Abbreviation': 'state', 'Name': 'county'}, inplace=True)
df_health.rename(columns=lambda x: x.lower().replace(' ','_'), inplace=True)

#%% IMPORT CLEAN ELECTION DATA
df_election = pd.read_csv('county_election_data_clean.csv')

#%% DATAFRAME WRANGLING

# Dropping AK
df_covid.set_index('state', inplace=True)
df_covid.drop('AK', axis=0, inplace=True)
df_covid.reset_index(inplace=True)

df_health.set_index('state', inplace=True)
df_health.drop('AK', axis=0, inplace=True)
df_health.reset_index(inplace=True)

df_election.set_index('state', inplace=True)
df_election.drop('AK', axis=0, inplace=True)
df_election.reset_index(inplace=True)

# Sort Values
df_covid.sort_values(by=['state', 'county'], inplace=True)
df_health.sort_values(by=['state', 'county'], inplace=True)
df_election.sort_values(by=['state', 'county'], inplace=True)


#%% CREATING UNIQUE ALPHANUMERIC COUNTY IDENTIFIERS PT 1

# Format county column so both dfs match
word = ['county', 'parish', 'city']
def format_df(dataframe, column, words):
    for word in range(len(words)):
        for i in range(len(dataframe)):
            if words[word] in dataframe[column][i]:
                dataframe[column][i] = dataframe[column][i][:len(dataframe[column][i])-len(words[word])].strip()
            else:
                pass
    
## Formatting df_election county
for i in range(len(df_election)):
    if '[' in df_election.county[i]:
        x = df_election['county'][i].split('[')[0]
        df_election['county'][i] = x.strip()
    else:
        pass
df_election['county_id'] = df_election['county'].apply(lambda x: x.lower().replace(' ',''))
format_df(df_election, 'county_id', word)

## Formatting df_health county names
df_health['county_id'] = df_health['county'].apply(lambda x: x.lower().replace(' ',''))
format_df(df_health, 'county_id', word)

## Formatting df_covid county names
df_covid['county_id'] = df_covid['county'].apply(lambda x: x.lower().replace(' ',''))
format_df(df_covid, 'county_id', word)

df_covid.reset_index(inplace=True, drop=True)
df_health.reset_index(inplace=True, drop=True)
df_election.reset_index(inplace=True, drop=True)

#%% MORE DATA ISSUES

# Find symmetric difference of all 3 data sets
df_covid1 = df_covid[['state','county_id']]
df_health1 = df_health[['state','county_id']]
df_election1 = df_election[['state','county_id']]

diff1 = df_covid1[~df_covid1.apply(tuple,1).isin(df_health1.apply(tuple,1))]
diff2 = df_health1[~df_health1.apply(tuple,1).isin(df_election1.apply(tuple,1))]
diff3 = df_election1[~df_election1.apply(tuple,1).isin(df_covid1.apply(tuple,1))]
diff = pd.concat([diff1, diff2, diff3])

df_covid = df_covid[df_covid['county_id'] != 'kalawao']
df_health = df_health[df_health['county_id'] != 'kalawao']
df_election = df_election[df_election['county_id'] != 'kalawao']

df_covid = df_covid[df_covid['county_id'] != 'kansas']
df_health = df_health[df_health['county_id'] != 'kansas']
df_election = df_election[df_election['county_id'] != 'kansas']

df_covid = df_covid[df_covid['county_id'] != 'do????aana']
df_health = df_health[df_health['county_id'] != 'do????aana']
df_election = df_election[df_election['county_id'] != 'do????aana']

df_covid = df_covid[df_covid['county_id'] != 'donaana']
df_health = df_health[df_health['county_id'] != 'donaana']
df_election = df_election[df_election['county_id'] != 'donaana']

#%% CREATING UNIQUE ALPHANUMERIC COUNTY IDENTIFIERS PT 2

df_covid.sort_values(by=['state', 'county_id'], inplace=True)
df_health.sort_values(by=['state', 'county_id'], inplace=True)
df_election.sort_values(by=['state', 'county_id'], inplace=True)

df_covid.reset_index(inplace=True, drop=True)
df_health.reset_index(inplace=True, drop=True)
df_election.reset_index(inplace=True, drop=True)

def replaceDuplicates(names):
    hash = {}
    for i in range(len(names)):
        if names[i] not in hash:
            hash[names[i]] = 1
        else:
            count = hash[names[i]]
            hash[names[i]] += 1
            names[i] += str(count)
    for i in range(len(names)):
        print(names[i], end = ' ')
 
names = df_covid['county_id']
names = names.to_list()
replaceDuplicates(names)

df_covid['county_id'] = names
df_health['county_id'] = names
df_election['county_id'] = names

#%% JOINING TO CREATE MASTER DF

# Left join first for df with least rows
df = pd.merge(df_covid, df_health, how='inner', left_on=['county_id'], right_on=['county_id'])
df = pd.merge(df, df_election, how='inner', left_on=['county_id'], right_on=['county_id'])

df.drop('population_raw_value', axis=1, inplace=True)
df.drop('state_x', axis=1, inplace=True)
df.drop('county_x', axis=1, inplace=True)
df.drop('state_y', axis=1, inplace=True)
df.drop('county_y', axis=1, inplace=True)

df = df[['state',
        'county',
        'county_id',
        'population',
        'metrics.testPositivityRatio',
        'metrics.caseDensity',
        'metrics.infectionRate',
        'metrics.infectionRateCI90',
        'metrics.icuCapacityRatio',
        'actuals.cases',
        'actuals.deaths',
        'actuals.hospitalBeds.capacity',
        'actuals.hospitalBeds.currentUsageTotal',
        'actuals.hospitalBeds.currentUsageCovid',
        'actuals.icuBeds.capacity',
        'actuals.icuBeds.currentUsageTotal',
        'actuals.icuBeds.currentUsageCovid',
        'actuals.newCases',
        'actuals.vaccinationsInitiated',
        'actuals.vaccinationsCompleted',
        'metrics.vaccinationsInitiatedRatio',
        'metrics.vaccinationsCompletedRatio',
        'actuals.newDeaths',
        'actuals.vaccinesAdministered',
        'cdcTransmissionLevel',
        'actuals.vaccinationsAdditionalDose',
        'metrics.vaccinationsAdditionalDoseRatio',
        'poor_or_fair_health_raw_value',
        'adult_smoking_raw_value',
        'adult_obesity_raw_value',
        'physical_inactivity_raw_value',
        'excessive_drinking_raw_value',
        'sexually_transmitted_infections_raw_value',
        'uninsured_raw_value',
        'ratio_of_population_to_primary_care_physicians.',
        'flu_vaccinations_raw_value',
        'high_school_completion_raw_value',
        'unemployment_raw_value',
        'children_in_poverty_raw_value',
        'income_inequality_raw_value',
        'violent_crime_raw_value',
        'percentage_of_households_with_overcrowding',
        'life_expectancy_raw_value',
        'child_mortality_raw_value',
        'infant_mortality_raw_value',
        'diabetes_prevalence_raw_value',
        'hiv_prevalence_raw_value',
        'food_insecurity_raw_value',
        'drug_overdose_deaths_raw_value',
        'median_household_income_raw_value',
        'homicides_raw_value',
        'firearm_fatalities_raw_value',
        '%_below_18_years_of_age_raw_value',
        '%_65_and_older_raw_value',
        '%_non-hispanic_black_raw_value',
        '%_american_indian_&_alaska_native_raw_value',
        '%_asian_raw_value',
        '%_hispanic_raw_value',
        '%_non-hispanic_white_raw_value',
        '%_females_raw_value',
        '%_rural_raw_value',
        'total_vote',
        'republican',
        'democratic',
        'independent',
        'rep_total_vote',
        'dem_total_vote',
        'independent_total_vote',
        'rep_maj_vote',
        'dem_maj_vote',
        'plurality_D',
        'plurality_R',
        'plurality_count']]


#%% DEALING WITH NAs

df.isna().sum()

# drop columns where # of NAs > 25% of df (777 rows)
cols = df.columns.to_list()
for col in cols:
    if df[col].isna().sum() > (0.25*len(df)):
        print(col)
        df.drop(col, axis=1, inplace=True)
    else:
        pass

# Imputa NAs with mean
cols = df.columns.to_list()
for col in cols:
    if df[col].isna().sum() > 1:
        df[col].fillna(df[col].mean(), inplace=True)

df.dropna(inplace=True)

#df.to_csv("clean_working_master_df.csv", index= False)

#%% DATA VISUALIZATION - CORRELATION HEATMAP

# Highlight unique relationships in the data
# =============================================================================
# df_corr = df[['metrics.vaccinationsInitiatedRatio', 'metrics.infectionRate',
#               'metrics.vaccinationsCompletedRatio', 'poor_or_fair_health_raw_value',
#               'adult_smoking_raw_value', '']]
# =============================================================================

# Full Correlation Heatmap (0.35 correlation cutoff)
df_corr = df.corr()
df_corr = df_corr.loc[(df_corr['metrics.vaccinationsInitiatedRatio'] > 0.35)|
                      (df_corr['metrics.vaccinationsInitiatedRatio'] < -0.35)]

plt.figure(figsize=(140,30))
sns.set_theme(font_scale=2.5, font="Arial")
sns.heatmap(df_corr, annot=True)

#%% LINEAR REGRESSION ANALYSIS

x = df.drop(columns=['metrics.vaccinationsInitiatedRatio', 'metrics.vaccinationsCompletedRatio', 
                     'metrics.vaccinationsAdditionalDoseRatio', 'actuals.vaccinationsAdditionalDose',
                     'actuals.vaccinationsCompleted', 'actuals.vaccinationsInitiated',
                     'state','county', 'county_id'], axis=1)
y = df['metrics.vaccinationsInitiatedRatio']

x_train, x_test, y_train, y_test = train_test_split(x,y,test_size=0.3, random_state=1)
scaler =MinMaxScaler()
x_train_scaled = scaler.fit_transform(x_train)
x_test_scaled = scaler.transform(x_test)
y_train_scaled = scaler.fit_transform(np.array(y_train).reshape(-1,1))
y_test_scaled = scaler.transform(np.array(y_test).reshape(-1,1))

model = LinearRegression()
model.fit(x_train_scaled, y_train_scaled)
y_pred = model.predict(x_test_scaled)
lin_rmse = mean_squared_error(y_test_scaled, y_pred, squared=False) #0.079 #0.100

# Linear Regression Feature Importance
model = LinearRegression()
model.fit(x, y)
importance = model.coef_
for i,v in enumerate(importance):
	print('Feature: %0d, Score: %.5f' % (i,v))
plt.bar([x for x in range(len(importance))], importance)
plt.show()

feat_import = pd.DataFrame({'feature': x.columns.to_list(),
                            'importance': importance})
feat_import.sort_values(by='importance', inplace=True)

# Get 10 lowest and 10 highest variables
f_lowest = feat_import.nsmallest(n=12, columns=['importance'], keep='all')
f_highest = feat_import.nlargest(n=12, columns=['importance'], keep='all')
all_feats = pd.concat([f_highest, f_lowest])

df_model = df[df.columns.intersection(all_feats['feature'])]


#%% XGBOOST REGRESSION ANALYSIS

# X, Y, train test split
x = df.drop(columns=['metrics.vaccinationsInitiatedRatio', 'metrics.vaccinationsCompletedRatio', 
                     'metrics.vaccinationsAdditionalDoseRatio', 'actuals.vaccinationsAdditionalDose',
                     'actuals.vaccinationsCompleted', 'actuals.vaccinationsInitiated',
                     'state','county', 'county_id'], axis=1)
y = df['metrics.vaccinationsInitiatedRatio']

x_train, x_test, y_train, y_test = train_test_split(x,y,test_size=0.3, random_state=1)

scaler =MinMaxScaler()
x_train_scaled = scaler.fit_transform(x_train)
x_test_scaled = scaler.transform(x_test)
y_train_scaled = scaler.fit_transform(np.array(y_train).reshape(-1,1))
y_test_scaled = scaler.transform(np.array(y_test).reshape(-1,1))

# Build model and make predictions
xgb_r = xgb.XGBRegressor(booster='gblinear', objective ='reg:squarederror', n_estimators = 10, seed = 123)
xgb_r.fit(x_train_scaled, y_train_scaled)
y_pred = xgb_r.predict(x_test_scaled)

# Check model accuracy
rmse = mean_squared_error(y_test_scaled, y_pred, squared=False) #0.107

# Tuning
params = {
        'min_child_weight': [1, 3, 5, 7, 10],
        'gamma': [0, .1, .3, .5, 1, 1.5, 2, 5],
        'subsample': [0.6, 0.8, 1.0],
        'colsample_bytree': [.4, 0.6, 0.8, 1.0],
        'max_depth': [ 3, 4, 5, 6, 8, 10, 12, 15]
}

grid_search = GridSearchCV(estimator=xgb_r, param_grid = params, cv=3, verbose=1)
grid_search.fit(x_train_scaled, y_train_scaled)

print(grid_search.best_params_) #{'colsample_bytree': 0.8, 'gamma': 0.3, 'max_depth': 6, 'min_child_weight': 1, 'subsample': 0.8}

# Build tuned model
xgb_r = xgb.XGBRegressor(objective ='reg:squarederror', n_estimators = 10, seed = 123, colsample_bytree=0.8, 
                         min_child_weight=1, gamma=0.3, max_depth=6, subsample=0.8)
xgb_r.fit(x_train_scaled, y_train_scaled)
y_pred = xgb_r.predict(x_test_scaled)
rmse = mean_squared_error(y_test_scaled, y_pred, squared=False) #0.106

# XGB Feature Importance
feat_import = pd.DataFrame({'feature': x.columns.to_list(),
                            'importance': xgb_r.feature_importances_})
feat_import.sort_values(by=['importance'], ascending=False, inplace=True)

# Plot important features
feat_import = feat_import[feat_import['importance']>0.01]
plt.figure(figsize = (20, 18))
sns.set_theme(style="whitegrid", palette="bright", font_scale=2, font="Arial")
sns.barplot(x="importance", y="feature", data=feat_import)

# Model w/ new features
x_list = feat_import['feature']
x = df.loc[:, df.columns.isin(x_list)]
y = df['metrics.vaccinationsInitiatedRatio']

x_train, x_test, y_train, y_test = train_test_split(x,y,test_size=0.3, random_state=1)

x_train_scaled = scaler.fit_transform(x_train)
x_test_scaled = scaler.transform(x_test)
y_train_scaled = scaler.fit_transform(np.array(y_train).reshape(-1,1))
y_test_scaled = scaler.transform(np.array(y_test).reshape(-1,1))

# Train the model
# Best Params (new features): {'colsample_bytree': 0.8, 'gamma': 0, 'max_depth': 6, 'min_child_weight': 10, 'subsample': 1.0}
xgb_r = xgb.XGBRegressor(objective ='reg:squarederror', n_estimators = 10, seed = 123, colsample_bytree=0.8, 
                         min_child_weight=10, gamma=0, max_depth=6, subsample=1.0)
xgb_r.fit(x_train_scaled, y_train_scaled)

# Predicts vaccination rate
y_pred = xgb_r.predict(x_test_scaled)
print('XGBoost model RMSE: {0:0.4f}'. format(mean_squared_error(y_test_scaled, y_pred, squared=False))) #0.1005

# Model Checking - K-means cross validation
folds = KFold(n_splits = 5, shuffle = True, random_state = 100)
scores = cross_val_score(xgb_r, x_train_scaled, y_train_scaled, scoring='neg_root_mean_squared_error', cv=folds)
scores = cross_val_score(xgb_r, x_train_scaled, y_train_scaled, scoring='r2', cv=folds)
scores

#%% PCA ANALYSIS
# Scale data
scaler = MinMaxScaler()

X = df.drop(columns=['state','county', 'county_id'], axis=1)
x = scaler.fit_transform(X)

# Build PCA model - Dimensionality Reduction
pca = PCA(n_components = 5)
pca_df = pca.fit_transform(x)
pca_df = pd.DataFrame(data = pca_df, columns = ['PC1', 'PC2', 'PC3', 'PC4', 'PC5'])

pca_comp = pd.DataFrame(pca.components_, columns=list(X.columns))
pca_comp = pca_comp.T
pca_comp['feature'] = pca_comp.index
pca_comp.reset_index(inplace=True, drop=True)
pca_comp.rename(columns={0: 'PC1', 1: 'PC2', 2: 'PC3', 3:'PC4', 4:'PC5'}, inplace=True)
first_column = pca_comp.pop('feature')
pca_comp.insert(0, 'feature', first_column)

# VIZ 1 - Covid Vaccination
y = pd.cut(df['metrics.vaccinationsInitiatedRatio'],bins=[0,0.25,0.5,0.75,1],labels=[1,2,3,4])
pca_df = pd.concat([pca_df, y], axis = 1)
pca_df.dropna()

plt.figure(figsize=(15,15))
g = sns.scatterplot(x='PC1', y='PC2', hue='metrics.vaccinationsInitiatedRatio', data=pca_df, palette='rocket')
plt.legend(title='Vaccination Rate', loc='upper right', labels=['0% - 25%', '25% - 50%', '50% - 75%', '75% - 100%'])
plt.show(g)

# VIZ 3 - Political
y = df['plurality_D']
pca_df = pd.concat([pca_df, y], axis = 1)
pca_df.dropna()

plt.figure(figsize=(15,15))
sns.set_theme(font_scale=1.5, font="Arial", style="whitegrid")
sns.axes_style("ticks")
sns.scatterplot(x='PC1', y='PC2', hue='plurality_D', data=pca_df, palette='Set1', legend='full')
plt.legend(title='Political Leaning', labels=['Republican', 'Democrat'], loc='upper right')
plt.show()

# Analyzing Principal Components
pca.explained_variance_ratio_
# ~25% variance lost in pca analysis

lo1 = pca_comp.nsmallest(n=5, columns=['PC1'], keep='all')
hi1 = pca_comp.nlargest(n=5, columns=['PC1'], keep='all')
lo2 = pca_comp.nsmallest(n=5, columns=['PC2'], keep='all')
hi2 = pca_comp.nlargest(n=5, columns=['PC2'], keep='all')
lo3 = pca_comp.nsmallest(n=5, columns=['PC3'], keep='all')
hi3 = pca_comp.nlargest(n=5, columns=['PC3'], keep='all')
lo4 = pca_comp.nsmallest(n=5, columns=['PC4'], keep='all')
hi4 = pca_comp.nlargest(n=5, columns=['PC4'], keep='all')
lo5 = pca_comp.nsmallest(n=5, columns=['PC5'], keep='all')
hi5 = pca_comp.nlargest(n=5, columns=['PC5'], keep='all')

pc1 = pd.concat([lo1, hi1]) 
pc1 = pc1[['feature', 'PC1']]
pc1.sort_values(by='PC1', ascending=False, inplace=True)
# ~41% of variance
# Political component: strong positive democratic vote, vaccination rates
#                      strong negative republican vote, rural value

pc2 = pd.concat([lo2, hi2])
pc2 = pc2[['feature', 'PC2']]
pc2.sort_values(by='PC2', ascending=False, inplace=True)
# ~15% of variance
# Poverty component: strong positive poor health, food insecurity, child poverty, black community, rural value
#                    strong negative covid & flu vax rate, med hh income, excess. drinking, white community

pc3 = pd.concat([lo3, hi3])
pc3 = pc3[['feature', 'PC3']]
pc3.sort_values(by='PC3', ascending=False, inplace=True)
# ~9% of variance
# Rural democratic white communities, mostly insured

pc4 = pd.concat([lo4, hi4])
pc4 = pc4[['feature', 'PC4']]
pc4.sort_values(by='PC4', ascending=False, inplace=True)
# ~6% of variance

pc5 = pd.concat([lo5, hi5])
pc5 = pc5[['feature', 'PC5']]
pc5.sort_values(by='PC5', ascending=False, inplace=True)
# ~5% of variance

#%% K-MEANS CLUSTERING

# Scale the data
scaler = MinMaxScaler()
X = df.drop(columns=['state','county', 'county_id'], axis=1)
x = scaler.fit_transform(X)

# Clustering + PCA
pca = PCA(n_components = 5)
pca.fit(x)
pca_comp = pca.transform(x)
pca_comp = pd.DataFrame(data = pca_comp, columns = ['PC1', 'PC2', 'PC3', 'PC4', 'PC5'])

wcv = []
silk_score = []
for k in range(2, 10):
    km = KMeans(n_clusters=k, random_state=0)
    km.fit(pca_comp)
    wcv.append(km.inertia_)
    silk_score.append(silhouette_score(pca_comp, km.labels_))

plt.plot(range(2, 10), wcv)
plt.xlabel("Number of Clusters")
plt.ylabel("within cluster variation")
plt.show()

plt.plot(range(2, 10), silk_score)
plt.xlabel("Number of Clusters")
plt.ylabel("silk score")
plt.show()

kl = KneeLocator(range(2, 10), wcv, curve="convex", direction="decreasing")
kl.elbow #5

km = KMeans(n_clusters=5, random_state=0)
km.fit(pca_comp)
pca_comp['label']=km.labels_
pca_comp.drop(columns=['PC3','PC4','PC5'], axis=1, inplace=True)

# Plot Clusters
plt.figure(figsize=(15,15))
sns.set_theme(font_scale=1.5, font="Arial", style="whitegrid")
sns.axes_style("ticks")
g = sns.scatterplot(x='PC1', y='PC2', hue='label', data=pca_comp, palette='Paired', alpha=1, legend='full')
plt.legend(title='Cluster', loc='upper right', labels=['1','2','3','4','5'])
plt.show(g)

cluster_1 = pca_comp.loc[pca_comp['label']==0].describe()
cluster_2 = pca_comp.loc[pca_comp['label']==1].describe()
cluster_3 = pca_comp.loc[pca_comp['label']==2].describe()
cluster_4 = pca_comp.loc[pca_comp['label']==3].describe()
cluster_5 = pca_comp.loc[pca_comp['label']==4].describe()

