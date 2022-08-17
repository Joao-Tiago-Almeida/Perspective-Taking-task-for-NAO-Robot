import os
from cv2 import GEMM_2_T
import pandas as pd
import json
from datetime import datetime
import seaborn as sns
import matplotlib.pyplot as plt

def get_df_from_files() -> pd.DataFrame:

    # read the data from the PB task
    df_pb = pd.read_csv("Questionnaires/Prosocial Behaviour (Responses).csv")
    df_pt = pd.read_csv("Questionnaires/Final Questionnaire (Responses).csv", index_col='Please fill in your participant ID')
    df_pt.drop(index=0, inplace = True)

    df_all = pd.DataFrame() # creates a new dataframe that's empty

    # iterate over the results
    directory = "../program for the robot/Participants results/"
    for filename in os.listdir(directory):
        folder = os.path.join(directory, filename)

        if filename == 'test': continue

        # checking if it is a file
        if os.path.isdir(folder):

            try:    # PB_task
                # open the file
                with open(folder+"/stats.json")as file:
                    results = json.load(file)   # read the results

                # add the number of sentences read
                id = results["Number of the Participant"]
                n_columns = df_pb[df_pb["Please fill in your participant ID"]==id].shape[1]
                blank_spaces = df_pb[df_pb["Please fill in your participant ID"]==id].isna().sum().sum()


                # if participants didn't do the PB task 
                if df_pb[df_pb["Please fill in your participant ID"]==id].shape[0] == 0:
                    raise IndexError
                elif df_pt.loc[id]["Did you read sentences to the robot?"] == "No": # at least started the questionnaire
                    results["Approximately, how many more sentences are you willing to read to help the robot?"] = 0
                    results["Sentences read"] = 0
                    raise IndexError


                # if the participants reads everyting, adds the second lap. if they reach the 3rd lap, god :/
                bonus = 0
                if blank_spaces == 0:
                    for i, sentence in enumerate(df_pb[df_pb["Please fill in your participant ID"]==id].values[0]):
                        if "Finish the Task" == sentence:
                            bonus = i - 2
                            break
                
                results["Sentences read"] = n_columns - blank_spaces - 5 + bonus # discount the number of sections without sentences

                # sentences participants think they read
                results["Approximately, how many more sentences are you willing to read to help the robot?"] = df_pb[df_pb["Please fill in your participant ID"]==id]["Approximately, how many more sentences are you willing to read to help the robot?"].iloc[0]

                results["Prosocial behaviour stopping time"] = df_pb[df_pb["Please fill in your participant ID"]==id]["Timestamp"].iloc[0]
            
            except: pass
            finally:
                # append to the dataframe
                df_all = df_all.append(results, ignore_index=True)

    # Some the partial information of each question
    sum_partial_columns(df_all, "Mistakes")
    sum_partial_columns(df_all, "Help")
    sum_partial_columns(df_all, "Tries")
    sum_partial_columns(df_all, "Time")

    df_all.set_index("Number of the Participant", inplace=True)
    df_all = df_all.merge(df_pt, left_index=True, right_index=True, how="outer")
    df_all["What is your nationality?"] = df_all["What is your nationality?"].str.lower()
    df_all.rename(columns = {
        "How old are you?" : "Age",
        "What is your gender?" : "Gender",
        "What is your nationality?" : "Nationality",
        "What is the highest level of education you have completed?" : "Education",
        "What is your field, if it applies" : "Studies",
        "How many times have you interact with a social robot before? " : "Interactions with SORO",
        "How did you find the robot's communicative skills in instructing you to find the correct object?" : "Communicative skills [1-7]",
        "How much did you find yourself caring about the robot?" : "Caring [1-7]",
        "How likeable did you find the robot?" : "Likeable [1-7]",
        "How empathetic did you find the robot?" : "Empathetic [1-7]",
        "How great did you perceive the robot's need for collecting the speech data?" : "Need for collecting data [1-7]",
        "Approximately, how many more sentences are you willing to read to help the robot?" : "Sentences read prior guess",
        "Approximately, how many sentences do you think you read to the robot?" : "Sentences read post guess",
        "Group" : "Condition",
        "Total time" : "Total scanning time [min]",
        "Perspective Taking Task Time" : "Perspective taking task time [min]",
        "Did you feel the robot's instructions were easy to follow?" : "Instructions easy to follow [1-7]",
        "Timestamp" : "Submission time of the final questionnaire",
        "Prosocial Behaviour Starting Time" : "Prosocial behaviour starting time"
        }, inplace = True)

    # Time of the PT task
    df_all["Perspective taking task time [min]"] = df_all["Perspective taking task time [min]"]/60.0
    df_all["Total scanning time [min]"] = df_all["Total scanning time [min]"]/60.0

    # Time of the PB task
    df_all['Prosocial behaviour starting time'] = pd.to_datetime(df_all['Prosocial behaviour starting time'], format='%Y/%m/%d %H:%M:%S')
    df_all['Prosocial behaviour stopping time'] = pd.to_datetime(df_all['Prosocial behaviour stopping time'], format='%d/%m/%Y %H:%M:%S')
    df_all['Prosocial behaviour time [min]'] = df_all['Prosocial behaviour stopping time']-df_all['Prosocial behaviour starting time']
    df_all['Prosocial behaviour time [min]'] = df_all['Prosocial behaviour time [min]'].dt.total_seconds()/60.0
    df_all.loc[df_all['Prosocial behaviour time [min]']<0, 'Prosocial behaviour time [min]'] = pd.NaT

    df_all["Condition"].replace("control", "object-centred", inplace = True)
    df_all["Condition"].replace("robot", "robot-centred", inplace = True)
    df_all["Condition"].replace("human", "human-centred", inplace = True)

    return df_all

def sum_partial_columns(df, type:str):
    df[f"Total {type.lower()}"] = 0
    for i in range(1, 16):
        df[f"Total {type.lower()}"] += df[f"{type} Q{str(i)}"]

def sort_by_word(df:pd.DataFrame, main_word:str, *extras):# -> pd.DataFrame:
    """
    For every column that contains the main word, creates a column for the rest of the column's name, the counter and the rest of the attributes
    """
    keys = ["Instruction", "Occurrences", *extras]
    df_new = pd.DataFrame( columns = keys ) # creates a new dataframe that's empty

    # iterate each line
    for index, row in df.iterrows():
        # iterate over the columns containing the main word
        breakpoint
        for column in row.keys():
            if main_word in column:
                values = []     # clear the features vector

                # extract the fixed values, the sub type of the main word
                try:
                    values.append(int(column.replace(main_word,"").lstrip()))
                    values.append(df[column][index])
                except: 
                    pass # there was no number

                # extract the extra features like the group
                for e in extras:
                    try: values.append(df[e][index])
                    except: values.append(None) # column does not found
                
                # append everything in the dataset
                df_new = df_new.append(dict(zip(keys,values)), ignore_index=True)

    return df_new.sort_values(by=["Instruction"])

from scipy.stats import f_oneway
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from scipy.stats import ttest_ind
import pingouin as pg

def statistical(df, metric, fillna = 0):

    if fillna==False and type(fillna)==bool: df = df.dropna(subset = [metric])


    #perform one-way ANOVA
    anova = f_oneway(
        list(df[df["Condition"]=="object-centred"][metric].fillna(fillna)),
        list(df[df["Condition"]=="robot-centred"][metric].fillna(fillna)),
        list(df[df["Condition"]=="human-centred"][metric].fillna(fillna))
    )

    print(anova)

    # perform Tukey's test
    tukey = pairwise_tukeyhsd(endog=df[metric].fillna(fillna),
                            groups=df['Condition'],
                            alpha=0.05)

    # display results
    print(tukey)

    # compute the starts
    stars_boundaries = [5e-2, 1e-2, 1e-3, 1e-4]
    starts = ['*'*list(pair<=stars_boundaries).count(True) + " "*list(pair<=stars_boundaries).count(False) for pair in tukey.pvalues]

    print(f"""
============================
 group1 group2 pvalue  stars
----------------------------
control  human {tukey.pvalues[0]:.2e} {starts[0]}
control  robot {tukey.pvalues[1]:.2e} {starts[1]}
  human  robot {tukey.pvalues[2]:.2e} {starts[2]}
----------------------------
""")

# Correlation formula
def correlation(df, x1:list, x2:list):
    df_f = df.fillna(0)
    for i in x1:
        for j in x2:
            print(f"r( {i} , {j} ) = {df_f[i].corr(df_f[j]) :.3f}")

def comapre_ambiguity_sentences(df, qa, qna, m):
    df_Qambiguous = pd.DataFrame()
    for index, row in df.iterrows():
        for q in [qa, qna]:
            df_Qambiguous = df_Qambiguous.append(
                {
                    "Condition" : row["Condition"],
                    "Instruction" : f"I {q}",
                    "Results"   : row[f"{m} Q{q}"],
                    "Metric"    : m
                },
                ignore_index=True
            )

    return df_Qambiguous

def analysis_ambiguities(df, m):
    df_Qambiguous = pd.DataFrame()
    for index, row in df.iterrows():
        for q in ["1", "8", "15"]:
            df_Qambiguous = df_Qambiguous.append(
                {
                    "Condition" : row["Condition"],
                    "Instruction" : f"I {q}",
                    "Results"   : row[f"{m} Q{q}"],
                    "Metric"    : m
                },
                ignore_index=True
            )

    return df_Qambiguous

def boxplot(df, x, y, orient = "v", path="Plots", identifier:str="", aspect = 1, outliers = True):
    file_name = y+"_"+identifier if identifier!='' else y
    if orient == "h": x, y = y, x
    plt.figure(figsize=(6.0*aspect, 6.0))
    g = sns.boxplot(
        data=df,
        x=x,
        y=y,
        orient = orient,
        order = ["object-centred","robot-centred","human-centred"],
        showfliers = outliers
    )
    if x in ["Condition", "Objective metric"] and aspect<1:  plt.xticks(rotation=30)
    plt.savefig(f"./{path}/{file_name.replace(' ','_')}.pdf",bbox_inches='tight')    

def grouped_boxplot(df, x, y, hue, orient = "v", path="Plots", aspect = 1.5, identifier:str="", outliers = True):
    file_name = y+"_"+identifier if identifier!='' else y
    if orient == "h": x, y = y, x
    g = sns.catplot(
    data = df,
    x = x,
    y = y,
    hue = hue,
    kind = "box",
    orient = orient,
    hue_order = ["object-centred","robot-centred","human-centred"],
    legend_out = False,
    aspect = aspect,
    showfliers = outliers
    )
    if x in ["Condition", "Objective metric"] and aspect<1:  plt.xticks(rotation=30)
    plt.savefig(f"./{path}/{file_name.replace(' ','_')}.pdf",bbox_inches='tight')

def grouped_barplot(df:pd.DataFrame=sns.load_dataset("penguins"), x:str="species", y:str="body_mass_g", hue:str="sex", path:str="Plots",identifier="", aspect = 1.5, orient = "v") -> None:
    
    g = sns.catplot(
        data=df, kind="bar",
        x=x, y=y, hue=hue,
        ci="sd", capsize=0.2, errwidth=1,
        aspect = aspect,
        hue_order = ["object-centred","robot-centred","human-centred"],
        legend_out = False,
        orient = orient
    )
    if x in ["Condition", "Objective metric"] and aspect<1:  plt.xticks(rotation=30)
    filename=y+"_"+identifier
    plt.savefig(f"./{path}/{filename.replace(' ','_')}.pdf",bbox_inches='tight')

    breakpoint

def barplot(df, x, y, orient = "v", path="Plots", identifier:str="", aspect = 1):
    file_name = y+"_"+identifier if identifier!='' else y
    if orient == "h": x, y = y, x
    plt.figure(figsize=(6.0*aspect, 6.0))
    g = sns.barplot(
        data=df,
        x=x,
        y=y,
        orient = orient,
        order = ["object-centred","robot-centred","human-centred"],
        capsize = 0.25
    )
    if x in ["Condition", "Objective metric"] and aspect<1:  plt.xticks(rotation=30)
    plt.savefig(f"./{path}/{file_name.replace(' ','_')}.pdf",bbox_inches='tight')    

def main():

    df_all = get_df_from_files()

    """--------------------------------------------------Demography!--------------------------------------------------"""

    # participants per condition
    g1 = sns.countplot(
        x="Group",
        data=df_all,
        order = ["object-centred","robot-centred","human-centred"],
        orient="h",
        palette="muted", alpha=0.9,
        )
    g1.set(xlabel='Condition', ylabel='Number of Participants')
    g1.bar_label(g1.containers[0])
    plt.savefig("./Plots/Participants per Condition.png")
    plt.clf()


if __name__ == "__main__":
    main()

    breakpoint