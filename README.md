# Spinning Frequency Bands

## Author

**Sourav Mukherjee**  
PhD Student  
Room N2410  
University of Bremen  
Department of Communications Engineering (Arbeitsbereich Nachrichtentechnik)  
Otto-Hahn-Allee NW1  
D-28359 Bremen, Germany  
📧 [mukherjee@ant.uni-bremen.de](mailto:mukherjee@ant.uni-bremen.de)

---
### License
If you use the code in any way, please cite the original paper. 

---

## Paper

**Title**: *Spinning Bands for LEO Satellites: Interference Mitigation Through Dynamic Downlink-Uplink Band Allocation*  

---

## Tips

### Required Packages

- `skyfield`  
- `numpy`  
- `matplotlib`
- `cvxpy`
- `mosek`

### How to Run

In the terminal:

```bash
python3 main.py
```

To use **Iridium satellites**, replace the satellite file in `def satSelection` within:

```
root/utilis/network.py
```
Change `'starlink.txt'` to `'iridium.txt'`.

---

## 📁 Code Structure

```
root/
├── main.py
├── readme.txt
└── utilis/
    ├── __init__.py
    ├── starlink.txt
    ├── iridium.txt
    ├── components.py
    │   └── class UE
    │   └── class Satellite
    ├── network.py
    │   └── class Network
    │       ├── Parameters:
    │       │   └── numSat, numUE, central_loc, radius_km, time, UEs, satellites
    │       ├── def generateLayout()
    │       ├── def generateRandomLoc()
    │       ├── def satSelection()
    │       └── def footprint()
    ├── simulator.py
    │   └── class Simulator
    │       ├── Parameters:
    │       │   └── B, freqs, Ns, Nu, L, Network, nIter, antSpacing
    │       ├── def run()
    │       ├── def plot()
    │       └── def save()
    ├── optimizer.py
    │   └── class Optimizer
    │       └── def run()
    │           └── 'fractionalProgramming': uses `max_iter` to control convergence
    └── helper.py
        └── class Helper
            ├── def arrayResponse()
            ├── def getDistance()
            ├── def pathLoss()
            ├── def ecef_to_geodetic()
            ├── def azimuth_elevation_from_sat()
            ├── def channelAndPrecoder()
            ├── def getSINR()
            ├── def spin2Frequency()
            └── def twoWaySumRate()
```


How to run this:
python3 scripts/generate_experiment_jobs.py \
  --j-values 2 \
  --k-values 10 \
  --total-iterations 10 \
  --chunk-size 5 \
  --jobs-root Data/jobs \
  --output-root Data
---
