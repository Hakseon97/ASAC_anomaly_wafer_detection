## Validation Process

# 1. 일정한 시간(@5분)마다 py파일 실행하여 폴더 내의 모든 KLARF파일을 Dataframe으로 변환.
# 2. 그 Dataframe에서 Fast-Fourier 변환을 거친 뒤, Amplitude 값 추가.
# 3. 미리 학습된 모델로 해당 KLARF파일을 검증하여 연속적인 Defects이 나왔는지 검출.
# 4. 만약 검출되면, 해당 INDEX를 역추적하여 어떤 장비가 이상있는지 확인.
#  * 미리 저장되어있는 Dataframe의 시간을 최대 3일로 설정. 

import pandas as pd
import numpy as np
from scipy import interpolate
import matplotlib.pyplot as plt
import glob, os
from datetime import datetime
import re
import joblib


############################################################################################################################
## 1. 일정한 시간(@5분)마다 py파일 실행하여 폴더 내의 모든 KLARF파일을 Dataframe으로 변환.
#- 5분마다 py. file 실행하여 폴더 내 모든 klarf 파일 변환

file_path = glob.glob("klarf_storage/*")

def readfile(file_path):
    readlines = []
    with open(file_path, 'r') as f:
        i = 1
        while True:
            line = f.readline()
            if not line:
                break
            line = str(i) + ' ' + line
            readlines.append(line.strip('\n').strip(';').split(' '))
            i += 1    
    return readlines

# 설비정보 parsing
temp_df = pd.DataFrame()
fname = []
for i, fp in enumerate(file_path):
    dict_klarf = {}
    for line in readfile(fp):
        if not line[1].isnumeric():
            dict_klarf[line[1]] = ' '.join(line[2:])
    fname.append(fp.split('/')[1])
    temp = pd.DataFrame(dict_klarf, index=[i])
    temp_df = pd.concat([temp_df, temp])


temp_df['FileName'] = fname
cols = ['FileName']
cols.extend(temp_df.columns[:-1])

temp_df = temp_df[cols]

# unique값이 1인 columns 정리
singleCols = ['FileVersion',
 'TiffSpec',
 'SampleType',
 'SampleSize',
 'SampleOrientationMarkType',
 'OrientationMarkLocation',
 'DiePitch',
 'SampleCenterLocation',
 'InspectionTest',
 'SampleTestPlan',
 'AreaPerTest',
 'DefectRecordSpec',
 'DefectList',
 'SummarySpec',
 'SummaryList',
 'EndOfFile',
 'DefectList',
 'SummaryList']

    
# 위에서 정리한 columns에 이미 dataframe으로 만든 DefectList, SummaryList columns 추가
singleCols.extend(["DefectList", "SummaryList"])
temp_df.drop(columns=singleCols, inplace=True)

# column 비교 후 제거 함수
# 보존할 column = col1
# 제거할 column = col2
def eliminate(df, col1, col2):
    '''
    col1: 남길 컬럼
    col2: 제거할 컬럼
    '''
    if df[df[col1] != df[col2]].size == 0:
        df.drop(columns=col2, inplace=True)
    return df

# FileTimestamp column과 ResultTimestamp column이 동일하면 해당 컬럼 삭제
temp_df = eliminate(temp_df, "FileTimestamp", "ResultTimestamp")

# temp_df의 FileTimestamp를 datetime형으로 변환
# 현재 %m-%d-%y %H:%M:%S 형태로 되어있음. 이를 %Y-%m-%d %H:%M:%S
temp_df.FileTimestamp = temp_df.FileTimestamp.apply(lambda x: datetime.strptime(x, "%m-%d-%y %H:%M:%S"))

# A3D01, A3D02로 요약
temp_df.InspectionStationID = temp_df.InspectionStationID.apply(lambda x: x.strip('"').split('" "')[-1])

# "LotID", "DeviceID", "StepID", "WaferID" columns에 대해 " " 제거
temp_df[["LotID", "DeviceID", "StepID", "WaferID"]] = \
    temp_df[["LotID", "DeviceID", "StepID", "WaferID"]].applymap(lambda x: x.strip(' "'))
    
# WaferID column과 Slot column이 동일한지 확인.
# 동일하면 Slot column 제거
# 동일하지 않다면, Fab에 문제가 생긴것..
temp_df = eliminate(temp_df, "WaferID", "Slot")

# SetupID column에서 timestamp가 FileTimestamp와 일치하는지 확인.
# 완벽히 일치한다면 해당 timestamp만 제거.
if temp_df[temp_df.SetupID.apply(lambda x: datetime.strptime(x.split('"')[2].strip(' '), "%m-%d-%y %H:%M:%S"))
        != temp_df.FileTimestamp].size == 0:
    temp_df.SetupID = temp_df.SetupID.apply(lambda x: x.split('"')[1])

# 수정된 SetupID column에서 Metrology-Type이 StepID와 일치하는지 확인.
# 완벽히 일치한다면 해당 column 제거.
temp_df = eliminate(temp_df, 'StepID', 'SetupID')

# StepID의 column 통일
temp_df.StepID = temp_df.StepID.apply(lambda x: x.split('-')[0]
                                      + '-T' + x.split('-')[1][1:]
                                      + '-' + x.split('-')[2])

# TiffFilename column이 FileName column과 일치하면 제거.
temp_df[["FileName", "TiffFilename"]] = temp_df[["FileName", "TiffFilename"]].applymap(lambda x: x.split('.')[0])
temp_df = eliminate(temp_df, "FileName", "TiffFilename")

# WaferID에 LotID 정보 추가
temp_df.WaferID = temp_df.LotID.apply(lambda x: re.split('\d+', x)[0]+re.split('\D+', x)[1]) + '-' + temp_df.WaferID

# columns 이름 변경
# FileTimestamp -> Timestamp
# InspectionStationID -> MachineID
temp_df.rename(columns={'FileTimestamp': 'Timestamp',
                        'InspectionStationID': 'MachineID'}, inplace=True)

# columns 순서 변경
newcols = ['FileName', 'LotID', 'WaferID', 'Timestamp', 'MachineID', 'StepID', 'DeviceID']
temp_df = temp_df[newcols]

# timestamp 순으로 정렬
temp_df = temp_df.sort_values('Timestamp').reset_index(drop=True)

##
# Defect 정보 parsing
# DefectList를 dataframe으로 변환.
defectList = []
for fp in file_path:
    readlines = readfile(fp)
    for line in readlines:
        if line[1] == 'DefectList':
            defectRow = int(line[0])
        elif line[1] == 'SummarySpec':
            defectRowEND = int(line[0]) - 1
        else:
            continue
        
    defectCols = ['FILE']
    defectCols.extend(readlines[defectRow-2][3:])
    
    if readlines[defectRow][1].isnumeric():
        for line in readlines[defectRow:defectRowEND]:
            if len(line) == 18:
                temp = [os.path.split(fp)[1]]
                temp.extend(line[1:])
                defectList.append(temp)
    else:
        temp = [os.path.split(fp)[1]]
        temp.extend(np.zeros(17).tolist())
        defectList.append(temp)

temp_defectDF = pd.DataFrame(data=defectList, columns=defectCols)
temp_defectDF[["XINDEX", "YINDEX"]] = temp_defectDF[["XINDEX", "YINDEX"]].astype('int')

# Summary Spec.을 DataFrame으로 변환

summarySpec = []
for fp in file_path:
    readlines = readfile(fp)
    for line in readlines:
        if line[1] == 'SummarySpec':
            summaryRow = int(line[0])
            
    summaryCols = ['FILE']
    summaryCols.extend(readlines[summaryRow-1][3:])
    if readlines[summaryRow+1][1].isnumeric():
        temp = [fp.split('/')[1]]
        temp.extend(readlines[summaryRow+1][1:])
        summarySpec.append(temp)
    else:
        temp = [fp.split('/')[1]]
        temp.extend(np.zeros(5).tolist())
        summarySpec.append(temp)
summary_df = pd.DataFrame(data=summarySpec, columns=summaryCols, index=np.arange(len(file_path)))

# defect_df와 summary_df merge
defect_df = pd.merge(summary_df, temp_defectDF, how='inner', left_on='FILE', right_on='FILE')
print(f'{len(file_path)}개의 KLARF ==========> Dataframe "변환완료"\n')

# defect_df의 FILE columns 변경
defect_df.FILE = defect_df.FILE.apply(lambda x: x.split('.')[0])

# defect_df에 defects 정보 추가
defect_df["MAP"] = defect_df[["XINDEX", "YINDEX"]].apply(list, axis=1)
def appendFn(*listset):
    lst = []
    for list_ in listset:
        lst.append(list_)
    return lst

defect_temp = defect_df.groupby(['FILE'])["MAP"].apply(appendFn).reset_index()
defect_temp.MAP = defect_temp.MAP.apply(lambda x: np.array(x).squeeze(0))

df = pd.merge(temp_df, defect_temp, how='inner', left_on='FileName', right_on='FILE').drop(columns=["FILE", "FileName"])

############################################################################################################################
## 2. Dataframe에서 Fast-Fourier 변환을 거친 뒤, Amplitude 값 추가.
# hyperparameter
class cfg:
    seed = 1234
    n_window = 3 # 한 batch에 확인할 wafer 수 -> 10
    origin = [12.5, 13.5] # wafer의 원점 정의
    
# batch dataset visualization v2
def dist(origin, defects):
    if defects[0] == [0,0]:
        return [-1]
    distance = [-1]
    for i in range(len(defects)):
        dist = 0
        for j in range(len(defects[i])):
            dist += (origin[j]-defects[i][j])**2
        dist **= 1/2
        distance.append(int(dist))
    return distance

def theta(origin, defects):
    if defects[0] == [0,0]:
        return [-180]
    theta = [-180]
    for i in range(len(defects)):
        rc_x = defects[i][0] - origin[0]
        rc_y = defects[i][1] - origin[1]
        ang = int(np.rad2deg(np.arctan2(rc_y, rc_x)))
        theta.append(ang) # 가시성을 위해 rad -> deg
    return theta

df["Distance"] = df.MAP.apply(lambda x:dist(cfg.origin, x))
df["Degree"] = df.MAP.apply(lambda x:theta(cfg.origin, x))

def batch_graph(degree, distance, graph=True):
    intp = interpolate.interp1d(degree, distance, kind='linear') # linear, cubic, nearest ...
    xnew = np.arange(min(degree), max(degree), 0.1)
    
    if graph:
        fig = plt.figure(figsize=(5,2))
        plt.plot(degree, distance, "ro", xnew, intp(xnew))
        plt.xlim([-180, -180+360*cfg.n_window])
        plt.ylim([0, 20])
        xtick = np.array(degree) % 360
        plt.xticks(degree, xtick, rotation=45)
        plt.show()
    return intp, xnew

# FFT graph
def fft_graph(input, graph=True):
    Y = np.fft.fft(input)
    amp = abs(Y) * (2/len(Y))
    freq = np.fft.fftfreq(len(Y), 1/1000)

    amp = amp[0:20]
    freq = freq[0:20]
    
    if graph:
        plt.figure(figsize=(5,2))
        # plt.xlim(0,1)
        plt.stem(freq, amp)
        plt.grid(True)
        plt.show()
    return amp

cfg.sample_freq = 1000
# fft후, amplitude 값 컬럼 추가
def amp_data(input, sample_freq = cfg.sample_freq):
    Y = np.fft.fft(input)
    amp = abs(Y) * (2/len(Y))
    freq = np.fft.fftfreq(len(Y), 1/sample_freq)
    return amp[0:20] # 20개까지만 추가.

def add_amplitude(df):
    nRows = len(df) - cfg.n_window + 1
    for i in range(nRows):
        df_dist = df.Distance[i:cfg.n_window + i].tolist()
        batch_dist = []
        for dist in df_dist:
            try:
                for d in dist:
                    batch_dist.append(d)
            except:
                pass
            
        df_deg = df.Degree[i:cfg.n_window + i].tolist()
        batch_deg = []
        for n, deg in enumerate(df_deg):
            try:
                for d in deg:
                    batch_deg.append(d + 360*n)
            except:
                pass
            
        intp, xnew = batch_graph(batch_deg, batch_dist, False)
        df.at[i+cfg.n_window-1,"Amplitude"] = amp_data(intp(xnew)).astype('object')
    return df

machine_type = df["MachineID"].unique()
step_type = df["StepID"].unique()
device_type = df["DeviceID"].unique()

temp_df = pd.DataFrame()
case = 0
for m in machine_type:
    for s in step_type:
        for d in device_type:
            case += 1
            temp = df[(df.MachineID == m) & (df.StepID == s) & (df.DeviceID == d)].reset_index()
            if len(temp) == 0:
                continue
            
            temp = add_amplitude(temp)
            temp_df = pd.concat([temp_df, temp], axis=0)
temp_df = temp_df.sort_values(by='index').reset_index(drop=True)

amp_df = temp_df[["Amplitude"]]
amp_df = amp_df[amp_df.Amplitude.notnull()]

def make_amplitude_df(df):
    arr = np.array(df.Amplitude.iloc[0]).reshape(1,-1)
    cols = np.array([i for i in range(arr.shape[1])])
    idx = df.index
    for i in range(1,len(df)):
        arr = np.append(arr, df.Amplitude.iloc[i].reshape(1,-1), axis=0)
        
    df = pd.DataFrame(arr, columns=cols, index=idx)
    return df
test_df = make_amplitude_df(amp_df)

## 3. 미리 학습된 모델로 해당 KLARF파일을 검증하여 연속적인 Defects이 나왔는지 검출.
rf = joblib.load("./basic_rf.pkl")
pred = pd.DataFrame(rf.predict(test_df), index=test_df.index)

## 4. 만약 검출되면, 해당 INDEX를 역추적하여 어떤 장비가 이상있는지 확인.
idx = pred[pred[0] == 1].index
anomaly_df = df.iloc[idx,:]

print("검사시간: {}\n\n".format(datetime.now()))
if anomaly_df.MachineID.nunique() == 1:
    print('장비 {}에 대한 확인이 필요합니다.\n'.format(anomaly_df.MachineID.unique()))
if anomaly_df.StepID.nunique() == 1:
    print('검사방법 {}에 대한 확인이 필요합니다.\n'.format(anomaly_df.StepID.unique()))
if anomaly_df.DeviceID.nunique() == 1:
    print('제품공정 {}에 대한 확인이 필요합니다.\n'.format(anomaly_df.DeviceID.unique()))
if anomaly_df.LotID.nunique() == 1:
    print('Lot ID {}에 대한 확인이 필요합니다.\n'.format(anomaly_df.LotID.unique()))
