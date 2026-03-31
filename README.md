# EBPlateLite v1.1.2

Correzione definitiva dell'errore Plotly nella preview geometrica.

## Fix
Nella funzione `_edge_style()` i valori non validi per `dash` sono stati sostituiti con stili Plotly ammessi:
- semplice/hinged -> `solid`
- fisso -> `solid`
- elastico -> `dash`

## Avvio
```bash
pip install -r requirements.txt
streamlit run app.py
```
