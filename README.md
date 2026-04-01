# ProfiliAcciaio v1.5 - Verifica trave in accaiio

**ProfiliAcciaio v1.5** è un'applicazione web interattiva sviluppata in Python tramite il framework Streamlit. Lo strumento è progettato per supportare l'ingegnere strutturista nella classificazione e verifica formale di profili in acciaio (sezioni a I, U, L, profili cavi circolari, quadrati e rettangolari) in accordo con le normative Eurocodice 3 (EN 1993-1-1) e NTC 2018.

L'applicazione integra sia formule chiuse per la risoluzione rapida di elementi semplici, sia un modulo analitico avanzato (LTBeam-style) per il calcolo dell'instabilità flesso-torsionale sotto condizioni di carico e vincolo complesse.

## 📖 Fondamenti Teorici

Il motore di calcolo implementa rigorosamente i principi dell'Eurocodice 3 per la progettazione di elementi strutturali in acciaio:

1. **Classificazione della Sezione:**
   Il codice valuta la snellezza locale dei singoli elementi (ali e anime) attraverso il rapporto $c/t$, pesato sul parametro $\varepsilon = \sqrt{235/f_y}$. Le sezioni vengono categorizzate in 4 classi per flessione, compressione e pressoflessione, governando la transizione tra calcolo plastico, elastico e l'insorgenza dell'instabilità locale.

2. **Sezioni di Classe 4 e Proprietà Efficaci:**
   Per sezioni in cui la tensione critica di instabilità locale viene raggiunta prima dello snervamento, si utilizza il metodo delle larghezze efficaci. L'algoritmo valuta la snellezza della piastra $\lambda_p = \frac{c/t}{28.4\varepsilon\sqrt{k}}$ e calcola un fattore di riduzione $\rho$ per derivare le aree $A_{eff}$ e i moduli di resistenza efficaci $W_{eff}$.

3. **Instabilità Flessionale (Buckling):**
   La resistenza all'instabilità globale viene calcolata determinando in primo luogo il carico critico euleriano $N_{cr} = \frac{\pi^2 E I}{l_0^2}$. Si definisce quindi la snellezza adimensionale $\bar{\lambda}$ per ricavare il fattore d'imperfezione $\alpha$ (associato alla relativa curva di instabilità) e calcolare il coefficiente di riduzione $\chi = \frac{1}{\Phi + \sqrt{\Phi^2 - \bar{\lambda}^2}}$.

4. **Svergolamento e Instabilità Flesso-Torsionale:**
   Per tenere in conto la suscettibilità a instabilità per flessione laterale e torsione, il codice valuta il momento critico elastico $M_{cr}$. La formula considera i contributi della rigidezza torsionale pura (di de Saint Venant, $I_t$) e della rigidezza all'ingobbamento (Warping, $I_w$):
   $M_{cr} = C_1 \frac{\pi^2 E I_z}{(kL)^2}\sqrt{\frac{G I_t + \pi^2 E I_w/(k_w L)^2}{E I_z}}$.
   
5. **Formule di Interazione:**
   Le interazioni tra sforzo assiale ($N_{Ed}$) e momenti flettenti ($M_{y,Ed}, M_{z,Ed}$) vengono verificate computando tassi di sfruttamento $\eta$ tramite complessi coefficienti d'interazione ($k_y, k_z, k_{LT}$) che tengono conto della ridistribuzione delle plasticità e dell'amplificazione del secondo ordine.

## ✨ Caratteristiche

* **Database integrato:** Ampia libreria di sezioni standard europee (IPE, HEA, HEB, RHS, SHS, CHS, L, UPN, ecc.).
* **Controlli automatici completi:** Valutazione delle resistenze sezionali ($N_{pl,Rd}, M_{c,Rd}$) e di instabilità ($N_{b,Rd}, M_{b,Rd}$).
* **Analisi Avanzata LTBeam-style:** Modulo a discretizzazione ad elementi finiti (1D) per ricavare il momento critico $M_{cr}$ sotto distribuzioni di carico (concentrate e distribuite) asimmetriche e vincoli elastici o intermedi.
* **Rendering Interattivo:** Generazione di grafici 2D della geometria della sezione e sviluppo 3D della membratura tramite Plotly.
* **Gestione Progetti:** Salva e ripristina rapidamente i flussi di lavoro tramite import/export dell'input in formato JSON e scaricamento di summary in CSV.

## 📥 Requisiti

L'applicazione necessita di un ambiente Python configurato con le seguenti librerie:

* `streamlit >= 1.31`
* `pandas >= 1.5`
* `numpy >= 1.24`
* `plotly >= 5.18`
* `scipy >= 1.10`

## ⚙️ Installazione

1. Clona il repository:
   ```bash
   git clone https://github.com/tuo-utente/checksteelsection.git
   cd checksteelsection
   ```
2. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
3. Assicurati che il database Excel (`Profilario_EN_UNI.xlsx`) sia collocato nella stessa directory del file `src.py`.

## 🚀 Utilizzo

Avvia il server di Streamlit eseguendo:
```bash
streamlit run app.py
```

### Struttura degli Input

L'utente deve fornire interattivamente:
* **Parametri Normativi e Materiale:** Normativa di riferimento (NTC/EC3 con $\gamma_{M0}$ e $\gamma_{M1}$ preimpostati o personalizzati), e grado di acciaio (S235, S275, S355, S460) con $f_y$ esplicito.
* **Selezione del Profilo:** Filtro rapido sul foglio dati ed estrazione geometrica.
* **Azioni di Progetto:** Sforzo normale ($N_{Ed}$ in kN, positivo per compressione), e momenti flettenti ($M_{y,Ed}, M_{z,Ed}$ in kNm).
* **Parametri Geometrici e di Vincolo:** Lunghezze libere di inflessione ($l_{0y}, l_{0z}, L_{ltb}$ in m), coefficienti di vincolo per instabilità assiale ($k_y, k_z$) e ingobbamento ($k_w$), oltre al fattore per la distribuzione del momento $C_1$.
* **Configurazione LTBeam (Opzionale ma suggerita):** Discretizzazione (numero elementi $N$), vincoli complessi intermedi e carichi distribuiti/concentrati alle varie stese della trave.

### Struttura degli Output

L'app restituisce un output altamente granulare:
* **Coefficienti di Sicurezza ($\eta$):** Restituisce analiticamente indicatori di "NON OK" / "OK" basati sul rapporto $E_d / R_d \le 1.0$ per la sezione trasversale, l'instabilità ad asse singolo e l'instabilità combinata / flesso-torsionale.
* **Analisi Passo-Passo:** Pannelli espandibili mostrano le formule intermedie applicate (es. valori di $\phi$, $\chi$, $\lambda$) simulando un foglio di calcolo matematico manuale.
* **Report LTBeam:** Output tabellare per l'analisi dei segmenti che include la stima del momento critico $M_{cr}$, la posizione del momento massimo $x/L$, il rapporto $\mu = M_{cr} / M_{max}$ e diagrammi interattivi del taglio e del momento flettente lungo l'asse longitudinale.

## 🤝 Contributi

Contributi al miglioramento del codice e alla correzione di bug sono sempre i benvenuti. Siete pregati di fare un fork della repository, creare un branch con la vostra feature e presentare una Pull Request (PR) descrivendo in dettaglio l'integrazione proposta o le patch fornite.

***

*Questo README soddisfa le tue aspettative? Desideri che aggiunga ulteriori informazioni (ad esempio, licenza d'uso, ringraziamenti bibliografici specifici o badge dinamici in cima al documento)?*
