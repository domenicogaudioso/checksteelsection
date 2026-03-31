# -*- coding: utf-8 -*-
import json
import pandas as pd
import streamlit as st
from src import (
    WORKBOOK_NAME, GAMMA_MODES, STEEL_GRADES, VINCOLI_K, WARPING_KW, C1_PRESET,
    LTB_END_PRESETS, LTB_INPLANE, LTB_RESTRAINT_TYPES, # Nuove importazioni LTBeam
    load_profile_database, sort_database, get_row,
    InputElemento, validate_profile_input, classify_section, class4_effective_properties,
    section_resistances, check_element, summary_dataframe, notes,
    figura_sezione_2d, figura_sezione_3d, to_json_bytes,
    class_table, class4_table, resistance_table, buckling_table, ltb_table, interaction_table,
    ltbeam_style_analysis, ltbeam_input_table, ltbeam_results_table, ltbeam_diagram_figure, ltbeam_eigenmode_placeholder # Nuove importazioni LTBeam
)

st.set_page_config(page_title='ProfiliAcciaio', layout='wide')
st.title('ProfiliAcciaio v1.5 - Verifica dell’elemento e LTBeam-style')
st.caption('Versione completa: stile della v1.4 con tabelle e badge mantenuti, includendo il calcolo avanzato LTBeam-style della v1.5.')

DEFAULTS = {
    'gamma_mode':'NTC/EC3', 'gamma_M0':1.0, 'gamma_M1':1.0,
    'acciaio':'S355', 'fy':355.0,
    'sheet_name':'IPE_EN10365', 'designation':'IPE 300',
    'sort_by':'Wy', 'ascending':False,
    'l0y_m':3.0, 'l0z_m':3.0, 'L_ltb_m':5.0,
    'NEd_kN':0.0, 'MyEd_kNm':150.0, 'MzEd_kNm':0.0,
    'curve_y':'b', 'curve_z':'c', 'k_factor':1.0, 'kw_factor':1.0, 'C1':1.0, 'zg_mm':0.0,
    'vincolo_y':'Cerniera - Cerniera', 'vincolo_z':'Cerniera - Cerniera', 'warping_label':'Libero - Libero', 'c1_label':'Momento uniforme',
}

def badge(ok: bool, label: str, value: float | None):
    color = '#15803d' if ok else '#b91c1c'
    bg = '#dcfce7' if ok else '#fee2e2'
    val_txt = 'n/a' if value is None or pd.isna(value) else f'{value:.3f}'
    st.markdown(f"<div style='padding:10px 12px;border-radius:12px;background:{bg};border:1px solid {color};margin-bottom:8px'><b style='color:{color}'>{label}</b><br><span style='color:{color};font-size:1.1rem'>η = {val_txt} → {'OK' if ok else 'NON OK'}</span></div>", unsafe_allow_html=True)

db = load_profile_database()

with st.sidebar:
    st.header('Import / Export input')
    up = st.file_uploader('Reimporta input JSON', type=['json'])
    defaults = DEFAULTS.copy()
    if up is not None:
        try:
            defaults.update(json.load(up))
            st.success('Input importati correttamente.')
        except Exception:
            st.error('JSON non valido.')

    st.header('Normativa / γM')
    gamma_mode = st.selectbox('Set coefficienti', ['NTC/EC3', 'Altro'], index=['NTC/EC3','Altro'].index(defaults['gamma_mode']))
    gamma = GAMMA_MODES[gamma_mode].copy()
    if gamma_mode == 'Altro':
        gamma['gamma_M0'] = st.number_input('γM0 [-]', 0.50, 5.0, float(defaults['gamma_M0']), 0.01)
        gamma['gamma_M1'] = st.number_input('γM1 [-]', 0.50, 5.0, float(defaults['gamma_M1']), 0.01)
    else:
        st.info(f"γM0={gamma['gamma_M0']:.2f}  γM1={gamma['gamma_M1']:.2f}")

    st.header('Acciaio')
    acciaio = st.selectbox('Tipo acciaio', list(STEEL_GRADES.keys()), index=list(STEEL_GRADES.keys()).index(defaults['acciaio']))
    fy = st.number_input('fy [MPa]', 100.0, 700.0, float(STEEL_GRADES.get(acciaio, defaults['fy'])), 5.0)

    st.header('Database profili')
    famiglie = ['Tutte'] + sorted(db['SheetName'].unique().tolist())
    family_filter = st.selectbox('Famiglia / foglio', famiglie, index=famiglie.index(defaults['sheet_name']) if defaults['sheet_name'] in famiglie else 0)
    search_txt = st.text_input('Cerca denominazione', value='')
    sort_by = st.selectbox('Ordina per', ['Wy', 'Jy', 'g', 'Denominazione'], index=['Wy', 'Jy', 'g', 'Denominazione'].index(defaults['sort_by']))
    ascending = st.checkbox('Ordine crescente', value=bool(defaults['ascending']))

filtered = db.copy()
if family_filter != 'Tutte':
    filtered = filtered[filtered['SheetName'] == family_filter]
if search_txt.strip():
    filtered = filtered[filtered['Denominazione'].str.contains(search_txt, case=False, na=False)]
filtered = sort_database(filtered, sort_by, ascending)
if filtered.empty:
    st.error('Nessun profilo trovato con i filtri impostati.')
    st.stop()

with st.sidebar:
    designation = st.selectbox('Profilo', filtered['Denominazione'].tolist(), index=0)
    sheet_name = filtered[filtered['Denominazione'] == designation].iloc[0]['SheetName']

    st.header('Azioni e lunghezze')
    l0y_m = st.number_input('l0y [m]', 0.1, 100.0, float(defaults['l0y_m']), 0.1)
    l0z_m = st.number_input('l0z [m]', 0.1, 100.0, float(defaults['l0z_m']), 0.1)
    L_ltb_m = st.number_input('L per svergolamento [m]', 0.1, 100.0, float(defaults['L_ltb_m']), 0.1)
    NEd_kN = st.number_input('NEd [kN] (compressione positiva)', -50000.0, 50000.0, float(defaults['NEd_kN']), 10.0)
    MyEd_kNm = st.number_input('My,Ed [kNm]', -50000.0, 50000.0, float(defaults['MyEd_kNm']), 10.0)
    MzEd_kNm = st.number_input('Mz,Ed [kNm]', -50000.0, 50000.0, float(defaults['MzEd_kNm']), 10.0)
    curve_y = st.selectbox('Curva instabilità asse y', ['a0','a','b','c','d'], index=['a0','a','b','c','d'].index(defaults['curve_y']))
    curve_z = st.selectbox('Curva instabilità asse z', ['a0','a','b','c','d'], index=['a0','a','b','c','d'].index(defaults['curve_z']))

    st.header('Vincoli e parametri di stabilità')
    vincolo_y = st.selectbox('Vincolo asse y (preset → k)', list(VINCOLI_K.keys()), index=list(VINCOLI_K.keys()).index(defaults['vincolo_y']))
    if VINCOLI_K[vincolo_y] is None:
        k_y = st.number_input('k asse y [-]', 0.1, 5.0, float(defaults['k_factor']), 0.05)
    else:
        k_y = VINCOLI_K[vincolo_y]
        st.caption(f'k asse y = {k_y:.2f}')
    vincolo_z = st.selectbox('Vincolo asse z (preset → k)', list(VINCOLI_K.keys()), index=list(VINCOLI_K.keys()).index(defaults['vincolo_z']))
    if VINCOLI_K[vincolo_z] is None:
        k_z = st.number_input('k asse z [-]', 0.1, 5.0, float(defaults['k_factor']), 0.05)
    else:
        k_z = VINCOLI_K[vincolo_z]
        st.caption(f'k asse z = {k_z:.2f}')
    
    k_factor = max(k_y, k_z)
    warping_label = st.selectbox('Vincolo all’ingobbamento (preset → kw)', list(WARPING_KW.keys()), index=list(WARPING_KW.keys()).index(defaults['warping_label']))
    if WARPING_KW[warping_label] is None:
        kw_factor = st.number_input('kw ingobbamento [-]', 0.1, 5.0, float(defaults['kw_factor']), 0.05)
    else:
        kw_factor = WARPING_KW[warping_label]
        st.caption(f'kw = {kw_factor:.2f}')
    c1_label = st.selectbox('Diagramma del momento (preset → C1)', list(C1_PRESET.keys()), index=list(C1_PRESET.keys()).index(defaults['c1_label']))
    if C1_PRESET[c1_label] is None:
        C1 = st.number_input('C1 [-]', 0.1, 5.0, float(defaults['C1']), 0.05)
    else:
        C1 = C1_PRESET[c1_label]
        st.caption(f'C1 = {C1:.2f}')
    zg_mm = st.number_input('zg [mm]', -1000.0, 1000.0, float(defaults['zg_mm']), 5.0)

inp = InputElemento(
    gamma_mode=gamma_mode, gamma_M0=gamma['gamma_M0'], gamma_M1=gamma['gamma_M1'],
    acciaio=acciaio, fy=fy, sheet_name=sheet_name, designation=designation,
    l0y_m=l0y_m, l0z_m=l0z_m, L_ltb_m=L_ltb_m, NEd_kN=NEd_kN, MyEd_kNm=MyEd_kNm, MzEd_kNm=MzEd_kNm,
    curve_y=curve_y, curve_z=curve_z, k_factor=k_factor, kw_factor=kw_factor, C1=C1, zg_mm=zg_mm,
    sort_by=sort_by, ascending=ascending, vincolo_y=vincolo_y, vincolo_z=vincolo_z, warping_label=warping_label, c1_label=c1_label,
)

errs = validate_profile_input(inp)
if errs:
    for e in errs:
        st.error(e)
    st.stop()

row = get_row(db, inp.sheet_name, inp.designation)
classes = classify_section(row, inp.fy)
eff = class4_effective_properties(row, inp.fy, classes)
res = section_resistances(row, inp, classes, eff)
checks = check_element(row, inp, classes, eff, res)
df_sum = summary_dataframe(row, inp, classes, eff, res, checks)
notes_list = notes(row, classes, eff, checks)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric('Npl,Rd [kN]', f"{res['Npl_Rd_kN']:.0f}")
c2.metric('Nb,min,Rd [kN]', f"{min(res['Nb_y_Rd_kN'], res['Nb_z_Rd_kN']):.0f}")
c3.metric('Mcy,Rd [kNm]', f"{res['Mcy_Rd_kNm']:.1f}")
c4.metric('Mb,Rd [kNm]', f"{res['Mb_Rd_kNm']:.1f}" if not pd.isna(res['Mb_Rd_kNm']) else 'n/a')
c5.metric('η max', f"{max([v for v in [checks['eta_Nsec'], checks['eta_Nbuck'], checks['eta_sec'], checks['eta_inst'], checks['eta_ltb']] if not pd.isna(v)]):.3f}")

st.info('Nota sui vincoli: la app non può dedurre automaticamente i vincoli reali dalla sola sezione. Per questo li imposti esplicitamente nei preset o in modo personalizzato; i relativi k, kw e C1 entrano nei calcoli di instabilità e svergolamento.')

# --- Modifica: Aggiunta la TAB 4 per LTBeam-style ---
T1, T2, T3, T4, T5 = st.tabs(['Profilo', 'Database', 'Calcoli dettagliati', 'LTBeam-style', 'Note'])

with T1:
    left, right = st.columns([1.15, 1])
    with left:
        st.subheader('Proprietà del profilo')
        st.dataframe(df_sum, use_container_width=True, height=420)
        st.download_button('Scarica sintesi CSV', df_sum.to_csv(index=False).encode('utf-8'), 'profiliacciaio_elemento_sintesi.csv', 'text/csv')
        st.download_button('Salva input JSON', to_json_bytes(inp.__dict__), 'profiliacciaio_elemento_input.json', 'application/json')
    with right:
        st.subheader('Visualizzazione del profilo')
        st.plotly_chart(figura_sezione_2d(row), use_container_width=True)
        cva, cvb = st.columns(2)
        with cva:
            badge(checks['ok_Nsec'], 'Forza normale - sezione', checks['eta_Nsec'])
            badge(checks['ok_Nbuck'], 'Forza normale - instabilità', checks['eta_Nbuck'])
            badge(checks['ok_sec'], 'Pressoflessione - sezione', checks['eta_sec'])
        with cvb:
            badge(checks['ok_inst'], 'Instabilità flessione + compressione', checks['eta_inst'])
            if not pd.isna(checks['eta_ltb']):
                badge(checks['ok_ltb'], 'Svergolamento / flesso-torsione', checks['eta_ltb'])
            else:
                st.info('Svergolamento non valutato per questa famiglia di sezione.')
    st.subheader('Sviluppo 3D della trave')
    st.plotly_chart(figura_sezione_3d(row, length_m=max(inp.L_ltb_m, inp.l0y_m, inp.l0z_m)), use_container_width=True)

with T2:
    show_cols = ['SheetName','Denominazione','Norma','Categoria','Peso_P_kg_m','Inerzia_Jx_cm4','Wel_x_cm3','Area_A_cm2']
    st.caption(f"Righe filtrate: {len(filtered)}")
    st.dataframe(filtered[show_cols], use_container_width=True, height=560)

with T3:
    st.subheader('Formule e procedimento di calcolo')
    st.markdown('Le formule mostrate qui sotto sono le stesse effettivamente utilizzate nel codice per arrivare ai coefficienti e agli indici di verifica.')
    st.markdown('### 1) Classificazione della sezione')
    st.latex(r"\varepsilon = \sqrt{235/f_y}")
    st.dataframe(class_table(row, inp.fy, classes), use_container_width=True, height=290)

    st.markdown('### 2) Sezione efficace per classe 4')
    st.latex(r"\lambda_p = \frac{c/t}{28.4\,\varepsilon\,\sqrt{k}}")
    st.latex(r"\rho = 1 \;\text{se}\; \lambda_p \le 0.673, \qquad \rho = \frac{\lambda_p - 0.165}{\lambda_p^2} \;\text{altrimenti}")
    st.dataframe(class4_table(row, inp.fy, classes, eff), use_container_width=True, height=340)

    st.markdown('### 3) Resistenze della sezione')
    st.latex(r"N_{pl,Rd} = \frac{A_{eff}\,f_y}{\gamma_{M0}}")
    st.latex(r"M_{c,y,Rd} = \frac{W_{res,x}\,f_y}{\gamma_{M0}}, \qquad M_{c,z,Rd} = \frac{W_{res,y}\,f_y}{\gamma_{M0}}")
    st.dataframe(resistance_table(row, inp, res), use_container_width=True, height=260)

    st.markdown('### 4) Instabilità per forza normale')
    st.latex(r"N_{cr} = \frac{\pi^2 E I}{l_0^2}")
    st.latex(r"\bar\lambda = \sqrt{\frac{N_{pl,Rd}}{N_{cr}}}")
    st.latex(r"\phi = \frac{1}{2}\left[1 + \alpha(\bar\lambda - 0.2) + \bar\lambda^2\right]")
    st.latex(r"\chi = \frac{1}{\phi + \sqrt{\phi^2 - \bar\lambda^2}}")
    st.latex(r"N_{b,Rd} = \chi \frac{A_{eff} f_y}{\gamma_{M1}}")
    st.dataframe(buckling_table(inp, res), use_container_width=True, height=480)

    st.markdown('### 5) Svergolamento / instabilità flesso-torsionale')
    st.latex(r"M_{cr} = C_1 \frac{\pi^2 E I_z}{(kL)^2}\sqrt{\frac{G I_t + \pi^2 E I_w/(k_w L)^2}{E I_z}}")
    st.latex(r"\bar\lambda_{LT} = \sqrt{\frac{M_{ref}}{M_{cr}}}, \qquad M_{b,Rd} = \chi_{LT}\,M_{ref}")
    st.dataframe(ltb_table(inp, res), use_container_width=True, height=340)

    st.markdown('### 6) Verifiche finali di elemento')
    st.latex(r"\eta_{N,sez} = \frac{N_{Ed}}{N_{pl,Rd}}")
    st.latex(r"\eta_{N,inst} = \max\left(\frac{N_{Ed}}{N_{b,y,Rd}},\frac{N_{Ed}}{N_{b,z,Rd}}\right)")
    st.latex(r"\eta_{sec} = \left(\frac{N_{Ed}}{N_{pl,Rd}}\right)^2 + \left(\frac{M_{y,Ed}}{M_{Ny}}\right)^\beta + \left(\frac{M_{z,Ed}}{M_{Nz}}\right)^\beta")
    st.latex(r"\eta_{inst} = \frac{N_{Ed}}{N_{b,min,Rd}} + k_y\frac{M_{y,Ed}}{M_{c,y,Rd}} + k_z\frac{M_{z,Ed}}{M_{c,z,Rd}}")
    st.latex(r"\eta_{LT} = \frac{N_{Ed}}{N_{b,z,Rd}} + k_{LT}\frac{M_{y,Ed}}{M_{b,Rd}} + k_z\frac{M_{z,Ed}}{M_{c,z,Rd}}")
    st.dataframe(interaction_table(inp, res, checks), use_container_width=True, height=530)
    st.markdown('#### Stato finale delle verifiche')
    ra, rb, rc = st.columns(3)
    with ra:
        badge(checks['ok_Nsec'], 'Forza normale - sezione', checks['eta_Nsec'])
        badge(checks['ok_Nbuck'], 'Forza normale - instabilità', checks['eta_Nbuck'])
    with rb:
        badge(checks['ok_sec'], 'Pressoflessione - sezione', checks['eta_sec'])
        badge(checks['ok_inst'], 'Instabilità flessione + compressione', checks['eta_inst'])
    with rc:
        if not pd.isna(checks['eta_ltb']):
            badge(checks['ok_ltb'], 'Svergolamento / flesso-torsione', checks['eta_ltb'])

# --- Tab 4 Aggiuntiva LTBeam-style (Spacchettata e formattata) ---
with T4:
    st.subheader("Calcolo Instabilità Flesso-Torsionale (Modello LTBeam-style)")
    
    cA, cB = st.columns(2)
    with cA:
        ltb_L = st.number_input('Lunghezza L [m]', 0.5, 50.0, float(inp.L_ltb_m), 0.1, key='ltbL')
        ltb_N = st.slider('N elementi di discretizzazione', 50, 200, 100, 1, key='ltbN')
        ltb_end = st.selectbox('Preset vincoli LTB alle estremità', list(LTB_END_PRESETS.keys()), 0, key='ltbEnd')
        ltb_plane = st.selectbox('Supporti nel piano di flessione', LTB_INPLANE, 0, key='ltbPlane')
        M1 = st.number_input('Momento M1 [kNm]', -50000.0, 50000.0, 0.0, 10.0, key='ltbM1')
        M2 = st.number_input('Momento M2 [kNm]', -50000.0, 50000.0, -67.0, 10.0, key='ltbM2')
        q1 = st.number_input('Carico distribuito q1 [kN/m]', -1000.0, 1000.0, -0.5, 0.1, key='ltbq1')
        q2 = st.number_input('Carico distribuito q2 [kN/m]', -1000.0, 1000.0, -0.5, 0.1, key='ltbq2')
        
    points = []
    with cB:
        st.write("Carichi concentrati sul profilo")
        for i, (Fdef, xfdef) in enumerate([(-52.5, 0.33), (-52.5, 0.63), (0.0, 0.5)], 1):
            p_cols = st.columns([1.5, 2, 2])
            with p_cols[0]:
                ena = st.checkbox(f'Attiva P{i}', value=(i < 3), key=f'pen{i}')
            with p_cols[1]:
                F = st.number_input(f'P{i} - Forza F [kN]', -5000.0, 5000.0, float(Fdef), 1.0, key=f'pf{i}')
            with p_cols[2]:
                xf = st.number_input(f'P{i} - Posizione (x/L) [-]', 0.0, 1.0, float(xfdef), 0.01, key=f'px{i}')
            points.append({'enabled': ena, 'F': F, 'xf': xf})
            
    st.markdown("#### Vincoli intermedi")
    rr = []
    r1, r2, r3 = st.columns(3)
    for i, col in enumerate([r1, r2, r3], 1):
        with col:
            typ = st.selectbox(f'R{i} - Tipo vincolo', LTB_RESTRAINT_TYPES, 0 if i == 3 else 1, key=f'rt{i}')
            xf = st.number_input(f'R{i} - Posizione (x/L) [-]', 0.0, 1.0, 0.5 if i == 1 else 0.75 if i == 2 else 0.25, 0.01, key=f'rx{i}')
            z = st.number_input(f'R{i} - Quota z [mm]', -1000.0, 1000.0, 0.0, 5.0, key=f'rz{i}')
            Rv = st.number_input(f'R{i} - Molla Rv', -1.0, 10000.0, -1.0 if typ != 'Elastic springs' else 10.0, 1.0, key=f'rrv{i}')
            Rq = st.number_input(f'R{i} - Molla Rq', -1.0, 10000.0, 0.0 if typ != 'Elastic springs' else 40.0, 1.0, key=f'rrq{i}')
            rr.append({'type': typ, 'xf': xf, 'z': z, 'Rv': Rv, 'Rq': Rq})
            
    # Esecuzione del calcolo LTBeam
    ltres = ltbeam_style_analysis(row, ltb_L, ltb_end, ltb_plane, M1, M2, q1, q2, points, rr, ltb_N)
    
    st.divider()
    st.subheader("Risultati LTBeam-style")
    
    a, b, c = st.columns([1, 1, 1])
    with a:
        st.write("Riepilogo Parametri di Input")
        st.dataframe(ltbeam_input_table(points, rr, ltb_end, ltb_plane, ltb_N), use_container_width=True, height=320)
    with b:
        st.write("Sintesi Valori Caratteristici")
        st.dataframe(ltbeam_results_table(ltres), use_container_width=True, height=320)
    with c:
        st.write("Risultato principale")
        badge(ltres['mu'] >= 1.0, 'LTBeam-style: μ = Mcr/Mmax', ltres['mu'])
        st.markdown(f"**Mmax = {ltres['Mmax_kNm']:.2f} kNm**")
        st.markdown(f"**Mcr = {ltres['Mcr_kNm']:.2f} kNm**")
        st.markdown(f"**Posizione del Mmax (x/L) = {ltres['xmax_rel']:.3f}**")
        
    st.plotly_chart(ltbeam_diagram_figure(ltres), use_container_width=True)
    
    x, y = st.columns([1.1, 1])
    with x:
        st.write("Dettaglio segmenti analizzati")
        st.dataframe(ltres['segments'], use_container_width=True, height=280)
    with y:
        st.plotly_chart(ltbeam_eigenmode_placeholder(ltres), use_container_width=True)

with T5:
    st.markdown('### Osservazioni')
    for n in notes_list:
        st.markdown(f'- {n}')
    st.markdown(f'- Vincolo asse y selezionato: **{inp.vincolo_y}** → k preset/suggerito = **{inp.k_factor:.2f}**')
    st.markdown(f'- Vincolo asse z selezionato: **{inp.vincolo_z}** → k preset/suggerito = **{inp.k_factor:.2f}** (per LTB è usato il caso più gravoso fra i preset y/z)')
    st.markdown(f'- Vincolo all’ingobbamento: **{inp.warping_label}** → kw = **{inp.kw_factor:.2f}**')
    st.markdown(f'- Diagramma dei momenti: **{inp.c1_label}** → C1 = **{inp.C1:.2f}**')
    st.info('Versione completa con modulo avanzato LTBeam-style per verifiche personalizzate della membratura per l’instabilità flesso-torsionale.')