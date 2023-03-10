# ASAC_anomaly_wafer_detection
연속적 defect 탐지 모델

<h2>프로젝트 추진배경</h2>

- 반도체 제조공정 배경
    - 최근 AI/빅데이터 분야에서 데이터 처리량이 급증하면서, 고대역폭메모리(HBM)에 대한 수요가 증가함.
    - 하지만, HBM은 높은 기술적 난이도로 인해 기존 D램보다 비싼 가격대를 형성함. ~ $180/chip
    - **수율 조건을 만족하면서, 불량칩이 연속적으로 생성**되는 경우가 발생.

- 불량 원인
    - 진성불량 : 불량 판정을 받았으며, 실제로도 불량인 경우. ex) 적층된 웨이퍼 간 연결고리인 범프에 이물질이 혼입된 경우 발생.
    - 가성불량 : 불량 판정을 받았지만, 실제로는 정상인 경우. ex) 검사 장비에 이물질 부착으로 인한 측정 오류.

- 수율 조건을 만족하면서 불량칩이 연속적으로 발생한다면, 장기적으로 봤을 때 비용적인 손실이 매우 큼.

<h3>따라서, 수율조건을 만족하면서 연속적으로 결함이 발생할 때, 실시간으로 문제 원인을 분석하는 모델을 개발하고자 함.</h3>
