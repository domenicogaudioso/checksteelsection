# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

WORKBOOK_NAME = 'Profilario_EN_UNI.xlsx'
E_MODULUS = 210000.0
G_MODULUS = 81000.0

GAMMA_MODES = {
    'NTC/EC3': {'gamma_M0': 1.00, 'gamma_M1': 1.00},
    'Altro': {'gamma_M0': 1.00, 'gamma_M1': 1.00},
}

STEEL_GRADES = {'S235':235.0,'S275':275.0,'S355':355.0,'S460':460.0}

ALL_PROFILE_SHEETS = [
    'IPE_EN10365','HEA_EN10365','HEB_EN10365','HEM_EN10365','HLZ_EN10365','HL_EN10365','HD_EN10365','HP_EN10365',
    'UB_EN10365','UC_EN10365','IPN_EN10365','UPN_EN10365','UPE_EN10365','PFC_EN10365',
    'CHS_EN10210','RHS_EN10210','SHS_EN10210','RHS_EN10219','L_EN10056'
]

VINCOLI_K = {
    'Cerniera - Cerniera': 1.00,
    'Incastro - Cerniera': 0.70,
    'Incastro - Incastro': 0.50,
    'Mensola': 2.00,
    'Personalizzato': None,
}

WARPING_KW = {
    'Libero - Libero': 1.00,
    'Vincolato - Libero': 0.70,
    'Vincolato - Vincolato': 0.50,
    'Personalizzato': None,
}

C1_PRESET = {
    'Momento uniforme': 1.00,
    'Triangolare': 1.13,
    'Doppia curvatura': 0.90,
    'Personalizzato': None,
}

# --- NUOVE COSTANTI LTBEAM ---
LTB_END_PRESETS = {
    "Fork / fork (v, θ fixed; v' e θ' free)": {"k": 1.0, "kw": 1.0},
    "Fixed / fixed": {"k": 0.5, "kw": 0.5},
    "Fixed / fork": {"k": 0.7, "kw": 0.7},
    "Cantilever": {"k": 2.0, "kw": 2.0}
}
LTB_INPLANE = ["Hinged at both ends", "Cantilever"]
LTB_RESTRAINT_TYPES = ["None", "v and θ fixed", "v fixed", "θ fixed", "Elastic springs"]
# -----------------------------

@dataclass(frozen=True)
class InputElemento:
    gamma_mode: str
    gamma_M0: float
    gamma_M1: float
    acciaio: str
    fy: float
    sheet_name: str
    designation: str
    l0y_m: float
    l0z_m: float
    L_ltb_m: float
    NEd_kN: float
    MyEd_kNm: float
    MzEd_kNm: float
    curve_y: str
    curve_z: str
    k_factor: float
    kw_factor: float
    C1: float
    zg_mm: float
    sort_by: str = 'Wy'
    ascending: bool = False
    vincolo_y: str = 'Cerniera - Cerniera'
    vincolo_z: str = 'Cerniera - Cerniera'
    warping_label: str = 'Libero - Libero'
    c1_label: str = 'Momento uniforme'


def to_json_bytes(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')


def workbook_path() -> Path:
    return Path(__file__).resolve().parent / WORKBOOK_NAME


def validate_profile_input(inp: InputElemento) -> List[str]:
    errs: List[str] = []
    if inp.gamma_M0 <= 0 or inp.gamma_M1 <= 0:
        errs.append('I coefficienti γM devono essere positivi.')
    if inp.fy <= 0:
        errs.append('fy deve essere positivo.')
    if min(inp.l0y_m, inp.l0z_m, inp.L_ltb_m) <= 0:
        errs.append('Le lunghezze devono essere positive.')
    if min(inp.k_factor, inp.kw_factor, inp.C1) <= 0:
        errs.append('k, kw e C1 devono essere positivi.')
    if not workbook_path().exists():
        errs.append(f'Il file {WORKBOOK_NAME} non è presente nella stessa cartella di app.py e src.py.')
    return errs


def _standardize_columns(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    out = df.copy()
    out['SheetName'] = sheet_name
    if sheet_name == 'L_EN10056':
        out = out.rename(columns={
            'Profilo':'Denominazione',
            'a [mm]':'Altezza_h_mm',
            'b [mm]':'Base_b_mm',
            't [mm]':'Spessore_anima_tw_mm',
            'A [cm²]':'Area_A_cm2',
            'Iy [cm4]':'Inerzia_Jx_cm4',
            'Iz [cm4]':'Inerzia_Jy_cm4',
        })
        out['Norma'] = 'EN 10056'
        out['Categoria'] = 'L'
        out['Spessore_ala_tf_mm'] = out['Spessore_anima_tw_mm']
        out['Raggio_r_mm'] = np.nan
        out['Peso_P_kg_m'] = out['Area_A_cm2'] * 0.785
        out['Inerzia_It_cm4'] = np.nan
        out['Ingobbamento_Iw_cm6'] = np.nan
        out['Wel_x_cm3'] = out['Inerzia_Jx_cm4'] / (out['Altezza_h_mm']/20.0)
        out['Wel_y_cm3'] = out['Inerzia_Jy_cm4'] / (out['Base_b_mm']/20.0)
        out['Wpl_x_cm3'] = out['Wel_x_cm3'] * 1.10
        out['Wpl_y_cm3'] = out['Wel_y_cm3'] * 1.10
        out['Avx_cm2'] = np.nan
        out['Avy_cm2'] = np.nan
        out['Note'] = out.get('Note', np.nan)
    needed = [
        'Norma','Categoria','Denominazione','Altezza_h_mm','Base_b_mm','Spessore_anima_tw_mm','Spessore_ala_tf_mm','Raggio_r_mm',
        'Area_A_cm2','Peso_P_kg_m','Inerzia_Jx_cm4','Inerzia_Jy_cm4','Inerzia_It_cm4','Ingobbamento_Iw_cm6',
        'Wel_x_cm3','Wel_y_cm3','Wpl_x_cm3','Wpl_y_cm3','Avx_cm2','Avy_cm2','Note','SheetName'
    ]
    for c in needed:
        if c not in out.columns:
            out[c] = np.nan
    return out[needed]


def load_profile_database() -> pd.DataFrame:
    xls = pd.ExcelFile(workbook_path(), engine='openpyxl')
    frames = []
    for s in xls.sheet_names:
        if s not in ALL_PROFILE_SHEETS:
            continue
        frames.append(_standardize_columns(pd.read_excel(workbook_path(), sheet_name=s, engine='openpyxl'), s))
    all_df = pd.concat(frames, ignore_index=True)
    num_cols = [c for c in all_df.columns if c not in {'Norma','Categoria','Denominazione','Note','SheetName'}]
    for c in num_cols:
        all_df[c] = pd.to_numeric(all_df[c], errors='coerce')
    return all_df


def sort_database(df: pd.DataFrame, sort_by: str, ascending: bool) -> pd.DataFrame:
    mapping = {'Wy':'Wel_x_cm3', 'Jy':'Inerzia_Jx_cm4', 'g':'Peso_P_kg_m', 'Denominazione':'Denominazione'}
    col = mapping.get(sort_by, 'Wel_x_cm3')
    return df.sort_values(by=[col, 'Denominazione'], ascending=[ascending, True], na_position='last').reset_index(drop=True)


def family_shape(sheet_name: str) -> str:
    if sheet_name in {'IPE_EN10365','HEA_EN10365','HEB_EN10365','HEM_EN10365','HLZ_EN10365','HL_EN10365','HD_EN10365','HP_EN10365','UB_EN10365','UC_EN10365','IPN_EN10365'}:
        return 'I'
    if sheet_name in {'UPN_EN10365','UPE_EN10365','PFC_EN10365'}:
        return 'U'
    if sheet_name == 'L_EN10056':
        return 'L'
    if sheet_name == 'CHS_EN10210':
        return 'CHS'
    if sheet_name in {'RHS_EN10210','RHS_EN10219'}:
        return 'RHS'
    if sheet_name == 'SHS_EN10210':
        return 'SHS'
    return 'GEN'


def get_row(db: pd.DataFrame, sheet_name: str, designation: str) -> pd.Series:
    sel = db[(db['SheetName'] == sheet_name) & (db['Denominazione'] == designation)]
    if sel.empty:
        raise ValueError('Profilo non trovato nel database.')
    return sel.iloc[0]


def eps_from_fy(fy: float) -> float:
    return math.sqrt(235.0 / max(fy, 1e-9))


def classify_section(row: pd.Series, fy: float) -> Dict[str,int]:
    shape = family_shape(row['SheetName'])
    eps = eps_from_fy(fy)
    h = float(row['Altezza_h_mm']); b = float(row['Base_b_mm']); tw = float(row['Spessore_anima_tw_mm'])
    tf = float(row['Spessore_ala_tf_mm']) if not pd.isna(row['Spessore_ala_tf_mm']) else tw
    if shape == 'I':
        cfl = max((b - tw) / 2.0, 1e-9); lam_fl = cfl / max(tf, 1e-9)
        cweb = max(h - 2*tf, 1e-9); lam_web = cweb / max(tw, 1e-9)
        cls_fl = 1 if lam_fl <= 9*eps else 2 if lam_fl <= 10*eps else 3 if lam_fl <= 14*eps else 4
        cls_wc = 1 if lam_web <= 33*eps else 2 if lam_web <= 38*eps else 3 if lam_web <= 42*eps else 4
        cls_wb = 1 if lam_web <= 72*eps else 2 if lam_web <= 83*eps else 3 if lam_web <= 124*eps else 4
        return {'compressione': max(cls_fl, cls_wc), 'flessione': max(cls_fl, cls_wb), 'pressoflessione': max(cls_fl, cls_wc, cls_wb)}
    if shape == 'U':
        cfl = max(b - tw/2.0, 1e-9); lam_fl = cfl / max(tf,1e-9)
        cweb = max(h - 2*tf, 1e-9); lam_web = cweb / max(tw, 1e-9)
        cls_fl = 1 if lam_fl <= 9*eps else 2 if lam_fl <= 10*eps else 3 if lam_fl <= 14*eps else 4
        cls_wc = 1 if lam_web <= 33*eps else 2 if lam_web <= 38*eps else 3 if lam_web <= 42*eps else 4
        cls_wb = 1 if lam_web <= 72*eps else 2 if lam_web <= 83*eps else 3 if lam_web <= 124*eps else 4
        return {'compressione': max(cls_fl, cls_wc), 'flessione': max(cls_fl, cls_wb), 'pressoflessione': max(cls_fl, cls_wc, cls_wb)}
    if shape == 'L':
        t = tw; lam = max(h - t, b - t) / max(t,1e-9)
        cls = 1 if lam <= 9*eps else 2 if lam <= 10*eps else 3 if lam <= 15*eps else 4
        return {'compressione': cls, 'flessione': cls, 'pressoflessione': cls}
    if shape in {'RHS','SHS'}:
        c1 = max(b - 3*tw, 1e-9); c2 = max(h - 3*tw, 1e-9); lam = max(c1/tw, c2/tw)
        cls = 1 if lam <= 33*eps else 2 if lam <= 38*eps else 3 if lam <= 42*eps else 4
        return {'compressione': cls, 'flessione': cls, 'pressoflessione': cls}
    if shape == 'CHS':
        D = h; lam = D / max(tw, 1e-9)
        cls = 1 if lam <= 50*eps**2 else 2 if lam <= 70*eps**2 else 3 if lam <= 90*eps**2 else 4
        return {'compressione': cls, 'flessione': cls, 'pressoflessione': cls}
    return {'compressione': 3, 'flessione': 3, 'pressoflessione': 3}


def rho_plate(lambda_p: float) -> float:
    if lambda_p <= 0.673:
        return 1.0
    rho = (lambda_p - 0.165) / (lambda_p**2)
    return max(min(rho, 1.0), 0.0)


def class4_effective_properties(row: pd.Series, fy: float, classes: Dict[str,int]) -> Dict[str,float]:
    shape = family_shape(row['SheetName'])
    A = float(row['Area_A_cm2'])
    Wel_y = float(row['Wel_x_cm3']); Wel_z = float(row['Wel_y_cm3'])
    Wpl_y = float(row['Wpl_x_cm3']) if not pd.isna(row['Wpl_x_cm3']) else Wel_y
    Wpl_z = float(row['Wpl_y_cm3']) if not pd.isna(row['Wpl_y_cm3']) else Wel_z
    h = float(row['Altezza_h_mm']); b = float(row['Base_b_mm']); tw = float(row['Spessore_anima_tw_mm'])
    tf = float(row['Spessore_ala_tf_mm']) if not pd.isna(row['Spessore_ala_tf_mm']) else tw
    eps = eps_from_fy(fy)
    base = {'Aeff_cm2': A,'Weff_y_cm3': Wpl_y if classes['flessione']<=2 else Wel_y,'Weff_z_cm3': Wpl_z if classes['flessione']<=2 else Wel_z,
            'rho_flange': 1.0,'rho_web_comp': 1.0,'rho_web_bend': 1.0,'lambda_p_flange': np.nan,'lambda_p_web_comp': np.nan,'lambda_p_web_bend': np.nan}
    if classes['pressoflessione'] < 4:
        return base
    if shape == 'I':
        cfl = (b - tw) / 2.0; cweb = max(h - 2*tf, 1e-9)
        lam_fl = (cfl/tf) / (28.4 * eps * math.sqrt(0.43)); lam_web_c = (cweb/tw) / (28.4 * eps * math.sqrt(4.0)); lam_web_b = ((0.5*cweb)/tw) / (28.4 * eps * math.sqrt(23.9))
        rho_fl = rho_plate(lam_fl); rho_wc = rho_plate(lam_web_c); rho_wb = rho_plate(lam_web_b)
        A_fl_eff = (2 * rho_fl * cfl * tf + tw*2*tf) / 100.0; A_web_eff = (rho_wc * cweb * tw) / 100.0
        return {'Aeff_cm2': A_fl_eff + A_web_eff,'Weff_y_cm3': Wel_y * min(rho_fl, rho_wb),'Weff_z_cm3': Wel_z * rho_fl,
                'rho_flange': rho_fl,'rho_web_comp': rho_wc,'rho_web_bend': rho_wb,'lambda_p_flange': lam_fl,'lambda_p_web_comp': lam_web_c,'lambda_p_web_bend': lam_web_b}
    if shape == 'U':
        cfl = b - tw/2.0; cweb = max(h - 2*tf, 1e-9)
        lam_fl = (cfl/tf) / (28.4 * eps * math.sqrt(0.43)); lam_web_c = (cweb/tw) / (28.4 * eps * math.sqrt(4.0)); lam_web_b = ((0.5*cweb)/tw) / (28.4 * eps * math.sqrt(23.9))
        rho_fl = rho_plate(lam_fl); rho_wc = rho_plate(lam_web_c); rho_wb = rho_plate(lam_web_b)
        return {'Aeff_cm2': (2*rho_fl*cfl*tf + rho_wc*cweb*tw) / 100.0,'Weff_y_cm3': Wel_y * min(rho_fl, rho_wb),'Weff_z_cm3': Wel_z * rho_fl,
                'rho_flange': rho_fl,'rho_web_comp': rho_wc,'rho_web_bend': rho_wb,'lambda_p_flange': lam_fl,'lambda_p_web_comp': lam_web_c,'lambda_p_web_bend': lam_web_b}
    if shape == 'L':
        c1 = h - tw; c2 = b - tw; lam1 = (c1/tw) / (28.4 * eps * math.sqrt(0.43)); lam2 = (c2/tw) / (28.4 * eps * math.sqrt(0.43))
        rho1, rho2 = rho_plate(lam1), rho_plate(lam2); rho = min(rho1, rho2)
        return {'Aeff_cm2': ((rho1*c1*tw) + (rho2*c2*tw) + tw*tw) / 100.0,'Weff_y_cm3': Wel_y * rho,'Weff_z_cm3': Wel_z * rho,
                'rho_flange': rho,'rho_web_comp': rho,'rho_web_bend': rho,'lambda_p_flange': max(lam1, lam2),'lambda_p_web_comp': max(lam1, lam2),'lambda_p_web_bend': max(lam1, lam2)}
    if shape in {'RHS','SHS'}:
        c1 = max(b - 3*tw, 1e-9); c2 = max(h - 3*tw, 1e-9); lam = max((c1/tw), (c2/tw)) / (28.4 * eps * math.sqrt(4.0)); rho = rho_plate(lam)
        return {'Aeff_cm2': A*rho, 'Weff_y_cm3': Wel_y*rho, 'Weff_z_cm3': Wel_z*rho, 'rho_flange': rho, 'rho_web_comp': rho, 'rho_web_bend': rho,
                'lambda_p_flange': lam, 'lambda_p_web_comp': lam, 'lambda_p_web_bend': lam}
    if shape == 'CHS':
        D = h; lam = (D/tw) / (90 * eps**2); rho = 1.0 if lam <= 1.0 else max(1/lam, 0.5)
        return {'Aeff_cm2': A*rho, 'Weff_y_cm3': Wel_y*rho, 'Weff_z_cm3': Wel_z*rho, 'rho_flange': rho, 'rho_web_comp': rho, 'rho_web_bend': rho,
                'lambda_p_flange': lam, 'lambda_p_web_comp': lam, 'lambda_p_web_bend': lam}
    return {'Aeff_cm2': A*0.85, 'Weff_y_cm3': Wel_y*0.85, 'Weff_z_cm3': Wel_z*0.85, 'rho_flange': 0.85, 'rho_web_comp': 0.85, 'rho_web_bend': 0.85,
            'lambda_p_flange': np.nan, 'lambda_p_web_comp': np.nan, 'lambda_p_web_bend': np.nan}


def buckling_alpha(curve: str) -> float:
    return {'a0':0.13, 'a':0.21, 'b':0.34, 'c':0.49, 'd':0.76}.get(curve.lower(), 0.34)


def chi_factor(lambda_bar: float, curve: str) -> float:
    a = buckling_alpha(curve); phi = 0.5 * (1 + a*(lambda_bar-0.2) + lambda_bar**2)
    chi = 1.0 / (phi + math.sqrt(max(phi**2 - lambda_bar**2, 0.0)))
    return min(1.0, chi)


def section_resistances(row: pd.Series, inp: InputElemento, classes: Dict[str,int], eff: Dict[str,float]) -> Dict[str,float]:
    Aeff_mm2 = eff['Aeff_cm2'] * 100.0; Weff_y_mm3 = eff['Weff_y_cm3'] * 1000.0; Weff_z_mm3 = eff['Weff_z_cm3'] * 1000.0
    Wgross_y_mm3 = (float(row['Wpl_x_cm3']) if classes['flessione'] <= 2 and not pd.isna(row['Wpl_x_cm3']) else float(row['Wel_x_cm3'])) * 1000.0
    Wgross_z_mm3 = (float(row['Wpl_y_cm3']) if classes['flessione'] <= 2 and not pd.isna(row['Wpl_y_cm3']) else float(row['Wel_y_cm3'])) * 1000.0
    Npl_Rd = Aeff_mm2 * inp.fy / inp.gamma_M0 / 1e3
    Mcy_Rd = (Wgross_y_mm3 if classes['flessione'] < 4 else Weff_y_mm3) * inp.fy / inp.gamma_M0 / 1e6
    Mcz_Rd = (Wgross_z_mm3 if classes['flessione'] < 4 else Weff_z_mm3) * inp.fy / inp.gamma_M0 / 1e6
    Iy_mm4 = float(row['Inerzia_Jx_cm4']) * 1e4; Iz_mm4 = float(row['Inerzia_Jy_cm4']) * 1e4; A_mm2 = float(row['Area_A_cm2']) * 100.0
    iy_mm = math.sqrt(Iy_mm4 / max(A_mm2, 1e-9)); iz_mm = math.sqrt(Iz_mm4 / max(A_mm2, 1e-9))
    Ncr_y = math.pi**2 * E_MODULUS * Iy_mm4 / max((inp.l0y_m*1000.0)**2, 1e-9) / 1e3
    Ncr_z = math.pi**2 * E_MODULUS * Iz_mm4 / max((inp.l0z_m*1000.0)**2, 1e-9) / 1e3
    lambda_y = math.sqrt(max(Npl_Rd / max(Ncr_y, 1e-9), 0.0)); lambda_z = math.sqrt(max(Npl_Rd / max(Ncr_z, 1e-9), 0.0))
    chi_y = chi_factor(lambda_y, inp.curve_y); chi_z = chi_factor(lambda_z, inp.curve_z)
    alpha_y = buckling_alpha(inp.curve_y); alpha_z = buckling_alpha(inp.curve_z)
    Nb_y_Rd = chi_y * Aeff_mm2 * inp.fy / inp.gamma_M1 / 1e3; Nb_z_Rd = chi_z * Aeff_mm2 * inp.fy / inp.gamma_M1 / 1e3
    shape = family_shape(row['SheetName'])
    if shape in {'I','U','L'} and not pd.isna(row['Ingobbamento_Iw_cm6']):
        It_mm4 = max(float(row['Inerzia_It_cm4']) * 1e4 if not pd.isna(row['Inerzia_It_cm4']) else 0.0, 1e2)
        Iw_mm6 = max(float(row['Ingobbamento_Iw_cm6']) * 1e6 if not pd.isna(row['Ingobbamento_Iw_cm6']) else 0.0, 1e3)
        L = inp.L_ltb_m * 1000.0; k = max(inp.k_factor, 1e-6); kw = max(inp.kw_factor, 1e-6); C1 = max(inp.C1, 0.1)
        term = G_MODULUS*It_mm4 + (math.pi**2 * E_MODULUS * Iw_mm6) / max((kw*L)**2, 1e-9)
        Mcr = C1 * math.pi**2 * E_MODULUS * Iz_mm4 / max((k*L)**2, 1e-9) * math.sqrt(max(term/(E_MODULUS*Iz_mm4), 1e-12)) / 1e6
        Mref = max(Mcy_Rd * inp.gamma_M0 / max(inp.gamma_M1, 1e-9), 1e-9)
        lambda_lt = math.sqrt(max(Mref / max(Mcr,1e-9), 0.0)); curve_lt = 'a' if row['SheetName'] in {'IPE_EN10365','HEA_EN10365','HEB_EN10365','HEM_EN10365','HLZ_EN10365','HL_EN10365','HD_EN10365','HP_EN10365','UB_EN10365','UC_EN10365'} else 'c'
        alpha_lt = buckling_alpha(curve_lt); chi_lt = chi_factor(lambda_lt, curve_lt); Mb_Rd = chi_lt * Mref
    else:
        Mcr = np.nan; lambda_lt = np.nan; chi_lt = np.nan; Mb_Rd = np.nan; alpha_lt = np.nan
    return {'Aeff_mm2': Aeff_mm2,'Weff_y_mm3': Weff_y_mm3,'Weff_z_mm3': Weff_z_mm3,'Npl_Rd_kN': Npl_Rd,'Mcy_Rd_kNm': Mcy_Rd,'Mcz_Rd_kNm': Mcz_Rd,'iy_mm': iy_mm,'iz_mm': iz_mm,
            'Ncr_y_kN': Ncr_y,'Ncr_z_kN': Ncr_z,'lambda_y': lambda_y,'lambda_z': lambda_z,'alpha_y': alpha_y,'alpha_z': alpha_z,'chi_y': chi_y,'chi_z': chi_z,'Nb_y_Rd_kN': Nb_y_Rd,'Nb_z_Rd_kN': Nb_z_Rd,
            'Mcr_kNm': Mcr,'lambda_lt': lambda_lt,'alpha_lt': alpha_lt,'chi_lt': chi_lt,'Mb_Rd_kNm': Mb_Rd}


def check_element(row: pd.Series, inp: InputElemento, classes: Dict[str,int], eff: Dict[str,float], res: Dict[str,float]) -> Dict[str,float]:
    N = max(inp.NEd_kN, 0.0); My = abs(inp.MyEd_kNm); Mz = abs(inp.MzEd_kNm)
    eta_Nsec = N / max(res['Npl_Rd_kN'], 1e-9); eta_Nbuck = max(N / max(res['Nb_y_Rd_kN'],1e-9), N / max(res['Nb_z_Rd_kN'],1e-9))
    MNy = np.nan; MNz = np.nan; a_red = np.nan; beta = np.nan
    if classes['pressoflessione'] <= 2 and family_shape(row['SheetName']) == 'I':
        Aeff_mm2 = eff['Aeff_cm2'] * 100.0; b = float(row['Base_b_mm']); tf = float(row['Spessore_ala_tf_mm'])
        a_red = min((Aeff_mm2 - 2*b*tf) / max(Aeff_mm2, 1e-9), 0.5); n = N / max(res['Npl_Rd_kN'], 1e-9); beta = min(5*n, 1.0)
        MNy = res['Mcy_Rd_kNm'] * max((1-n)/(1-0.5*a_red), 0.0) if n <= a_red else res['Mcy_Rd_kNm']
        MNz = res['Mcz_Rd_kNm'] if n <= a_red else res['Mcz_Rd_kNm'] * max(1 - ((n-a_red)/(1-a_red))**2, 0.0)
        eta_sec = (N/max(res['Npl_Rd_kN'],1e-9))**2 + (My/max(MNy,1e-9))**beta + (Mz/max(MNz,1e-9))**beta
    else:
        eta_sec = N/max(res['Npl_Rd_kN'],1e-9) + My/max(res['Mcy_Rd_kNm'],1e-9) + Mz/max(res['Mcz_Rd_kNm'],1e-9)
    Nmin = min(res['Nb_y_Rd_kN'], res['Nb_z_Rd_kN'])
    if classes['pressoflessione'] <= 2:
        wg = float(row['Wel_x_cm3']); wp = float(row['Wpl_x_cm3']) if not pd.isna(row['Wpl_x_cm3']) else wg
        wg2 = float(row['Wel_y_cm3']); wp2 = float(row['Wpl_y_cm3']) if not pd.isna(row['Wpl_y_cm3']) else wg2
        mu_y = min(res['lambda_y']*(2.0-4.0) + max((wp-wg)/max(wg,1e-9), 0.0), 0.9); mu_z = min(res['lambda_z']*(2.0-4.0) + max((wp2-wg2)/max(wg2,1e-9), 0.0), 0.9)
    else:
        mu_y = min(res['lambda_y']*(2.0-4.0), 0.9); mu_z = min(res['lambda_z']*(2.0-4.0), 0.9)
    ky = max(1 - mu_y*N/max(res['Nb_y_Rd_kN']/max(inp.gamma_M1,1e-9), 1e-9), 0.2); kz = max(1 - mu_z*N/max(res['Nb_z_Rd_kN']/max(inp.gamma_M1,1e-9), 1e-9), 0.2)
    eta_inst = N/max(Nmin,1e-9) + ky*My/max(res['Mcy_Rd_kNm'],1e-9) + kz*Mz/max(res['Mcz_Rd_kNm'],1e-9)
    if not pd.isna(res['Mb_Rd_kNm']):
        mu_lt = min(0.15*res['lambda_lt'] - 0.15, 0.9); klt = max(1 - mu_lt*N/max(res['Nb_z_Rd_kN']/max(inp.gamma_M1,1e-9), 1e-9), 0.2)
        eta_ltb = N/max(res['Nb_z_Rd_kN'],1e-9) + klt*My/max(res['Mb_Rd_kNm'],1e-9) + kz*Mz/max(res['Mcz_Rd_kNm'],1e-9)
    else:
        mu_lt = np.nan; klt = np.nan; eta_ltb = np.nan
    return {'eta_Nsec': eta_Nsec,'eta_Nbuck': eta_Nbuck,'eta_sec': eta_sec,'eta_inst': eta_inst,'eta_ltb': eta_ltb,
            'ok_Nsec': eta_Nsec <= 1.0,'ok_Nbuck': eta_Nbuck <= 1.0,'ok_sec': eta_sec <= 1.0,'ok_inst': eta_inst <= 1.0,'ok_ltb': (eta_ltb <= 1.0) if not pd.isna(eta_ltb) else True,
            'MNy_kNm': MNy,'MNz_kNm': MNz,'a_red': a_red,'beta': beta,'mu_y': mu_y,'mu_z': mu_z,'ky': ky,'kz': kz,'mu_lt': mu_lt,'klt': klt}


def _fmt(v, nd=4):
    if v is None:
        return ''
    try:
        if pd.isna(v):
            return 'n/a'
    except Exception:
        pass
    if isinstance(v, str):
        return v
    return f'{float(v):.{nd}f}'


def class_table(row: pd.Series, fy: float, classes: Dict[str,int]) -> pd.DataFrame:
    shape = family_shape(row['SheetName']); eps = eps_from_fy(fy); h = float(row['Altezza_h_mm']); b = float(row['Base_b_mm']); tw = float(row['Spessore_anima_tw_mm']); tf = float(row['Spessore_ala_tf_mm']) if not pd.isna(row['Spessore_ala_tf_mm']) else tw
    lines = [{'Parametro':'ε','Formula':'ε = √(235/fy)','Sostituzione':f'√(235/{_fmt(fy,1)})','Risultato':_fmt(eps,4)}]
    if shape == 'I':
        cfl = (b-tw)/2.0; lam_fl = cfl/tf; cweb = h-2*tf; lam_web = cweb/tw
        lines += [
            {'Parametro':'c_flange [mm]','Formula':'c = (b - tw)/2','Sostituzione':f'({b:.1f} - {tw:.1f})/2','Risultato':_fmt(cfl,3)},
            {'Parametro':'λ_flange [-]','Formula':'λ = c/tf','Sostituzione':f'{_fmt(cfl,3)}/{tf:.3f}','Risultato':_fmt(lam_fl,3)},
            {'Parametro':'c_web [mm]','Formula':'c = h - 2 tf','Sostituzione':f'{h:.1f} - 2·{tf:.3f}','Risultato':_fmt(cweb,3)},
            {'Parametro':'λ_web [-]','Formula':'λ = c/tw','Sostituzione':f'{_fmt(cweb,3)}/{tw:.3f}','Risultato':_fmt(lam_web,3)},
            {'Parametro':'Classe compressione','Formula':'max(classe ala, classe anima-comp.)','Sostituzione':'secondo limiti semplificati implementati','Risultato':str(classes['compressione'])},
            {'Parametro':'Classe flessione','Formula':'max(classe ala, classe anima-fless.)','Sostituzione':'secondo limiti semplificati implementati','Risultato':str(classes['flessione'])},
            {'Parametro':'Classe pressoflessione','Formula':'max(classe compressione, classe flessione)','Sostituzione':'-','Risultato':str(classes['pressoflessione'])},
        ]
    else:
        lines += [
            {'Parametro':'Classe compressione','Formula':'limiti semplificati per famiglia','Sostituzione':'-','Risultato':str(classes['compressione'])},
            {'Parametro':'Classe flessione','Formula':'limiti semplificati per famiglia','Sostituzione':'-','Risultato':str(classes['flessione'])},
            {'Parametro':'Classe pressoflessione','Formula':'limiti semplificati per famiglia','Sostituzione':'-','Risultato':str(classes['pressoflessione'])},
        ]
    return pd.DataFrame(lines)


def class4_table(row: pd.Series, fy: float, classes: Dict[str,int], eff: Dict[str,float]) -> pd.DataFrame:
    lines = [
        {'Parametro':'A_eff [cm²]','Formula':'Aeff da riduzione degli elementi compressi','Sostituzione':'riduzione distinta flange/anima','Risultato':_fmt(eff['Aeff_cm2'],4)},
        {'Parametro':'W_eff,x [cm³]','Formula':'Weff,x da sezione efficace','Sostituzione':'riduzione coerente con la parte compressa','Risultato':_fmt(eff['Weff_y_cm3'],4)},
        {'Parametro':'W_eff,y [cm³]','Formula':'Weff,y da sezione efficace','Sostituzione':'riduzione coerente con la parte compressa','Risultato':_fmt(eff['Weff_z_cm3'],4)},
        {'Parametro':'λp_flange [-]','Formula':'λp = (c/t)/(28.4 ε √k)','Sostituzione':'elemento compresso implementato','Risultato':_fmt(eff['lambda_p_flange'],4)},
        {'Parametro':'ρ_flange [-]','Formula':'ρ = 1 se λp≤0.673; altrimenti (λp-0.165)/λp²','Sostituzione':'-','Risultato':_fmt(eff['rho_flange'],4)},
        {'Parametro':'λp_web,comp [-]','Formula':'λp = (c/t)/(28.4 ε √k)','Sostituzione':'elemento interno in compressione','Risultato':_fmt(eff['lambda_p_web_comp'],4)},
        {'Parametro':'ρ_web,comp [-]','Formula':'ρ = 1 se λp≤0.673; altrimenti (λp-0.165)/λp²','Sostituzione':'-','Risultato':_fmt(eff['rho_web_comp'],4)},
        {'Parametro':'λp_web,fless [-]','Formula':'λp = (c/t)/(28.4 ε √k)','Sostituzione':'parte compressa in flessione','Risultato':_fmt(eff['lambda_p_web_bend'],4)},
        {'Parametro':'ρ_web,fless [-]','Formula':'ρ = 1 se λp≤0.673; altrimenti (λp-0.165)/λp²','Sostituzione':'-','Risultato':_fmt(eff['rho_web_bend'],4)},
    ]
    return pd.DataFrame(lines)


def resistance_table(row: pd.Series, inp: InputElemento, res: Dict[str,float]) -> pd.DataFrame:
    lines = [
        {'Parametro':'Npl,Rd [kN]','Formula':'Npl,Rd = Aeff · fy / γM0','Sostituzione':f'{_fmt(res["Aeff_mm2"],2)} · {_fmt(inp.fy,1)} / {_fmt(inp.gamma_M0,2)} / 1000','Risultato':_fmt(res['Npl_Rd_kN'],4)},
        {'Parametro':'Mcy,Rd [kNm]','Formula':'Mcy,Rd = Wres,x · fy / γM0','Sostituzione':f'{_fmt(res["Weff_y_mm3"],2)} o Wres,x · {_fmt(inp.fy,1)} / {_fmt(inp.gamma_M0,2)} / 10^6','Risultato':_fmt(res['Mcy_Rd_kNm'],4)},
        {'Parametro':'Mcz,Rd [kNm]','Formula':'Mcz,Rd = Wres,y · fy / γM0','Sostituzione':f'{_fmt(res["Weff_z_mm3"],2)} o Wres,y · {_fmt(inp.fy,1)} / {_fmt(inp.gamma_M0,2)} / 10^6','Risultato':_fmt(res['Mcz_Rd_kNm'],4)},
        {'Parametro':'iy [mm]','Formula':'iy = √(Iy/A)','Sostituzione':'Iy e A lordi del profilario','Risultato':_fmt(res['iy_mm'],4)},
        {'Parametro':'iz [mm]','Formula':'iz = √(Iz/A)','Sostituzione':'Iz e A lordi del profilario','Risultato':_fmt(res['iz_mm'],4)},
    ]
    return pd.DataFrame(lines)


def buckling_table(inp: InputElemento, res: Dict[str,float]) -> pd.DataFrame:
    phi_y = 0.5 * (1 + res['alpha_y']*(res['lambda_y']-0.2) + res['lambda_y']**2); phi_z = 0.5 * (1 + res['alpha_z']*(res['lambda_z']-0.2) + res['lambda_z']**2)
    lines = [
        {'Parametro':'Ncr,y [kN]','Formula':'Ncr = π² E Iy / l0²','Sostituzione':f'π²·E·Iy/({inp.l0y_m:.3f}·1000)²','Risultato':_fmt(res['Ncr_y_kN'],4)},
        {'Parametro':'Ncr,z [kN]','Formula':'Ncr = π² E Iz / l0²','Sostituzione':f'π²·E·Iz/({inp.l0z_m:.3f}·1000)²','Risultato':_fmt(res['Ncr_z_kN'],4)},
        {'Parametro':'λ̄y [-]','Formula':'λ̄ = √(Npl,Rd / Ncr)','Sostituzione':f'√({_fmt(res["Npl_Rd_kN"],4)}/{_fmt(res["Ncr_y_kN"],4)})','Risultato':_fmt(res['lambda_y'],4)},
        {'Parametro':'αy [-]','Formula':'coefficiente curva di instabilità','Sostituzione':f'curva {inp.curve_y}','Risultato':_fmt(res['alpha_y'],4)},
        {'Parametro':'φy [-]','Formula':'φ = 0.5 [1 + α(λ̄-0.2) + λ̄²]','Sostituzione':f'0.5·[1 + {res["alpha_y"]:.4f}·({_fmt(res["lambda_y"],4)}-0.2) + {_fmt(res["lambda_y"],4)}²]','Risultato':_fmt(phi_y,4)},
        {'Parametro':'χy [-]','Formula':'χ = 1 / [φ + √(φ² - λ̄²)]','Sostituzione':'-','Risultato':_fmt(res['chi_y'],4)},
        {'Parametro':'Nb,y,Rd [kN]','Formula':'Nb,Rd = χ · Aeff · fy / γM1','Sostituzione':f'{_fmt(res["chi_y"],4)}·Aeff·fy/{_fmt(inp.gamma_M1,2)}','Risultato':_fmt(res['Nb_y_Rd_kN'],4)},
        {'Parametro':'λ̄z [-]','Formula':'λ̄ = √(Npl,Rd / Ncr)','Sostituzione':f'√({_fmt(res["Npl_Rd_kN"],4)}/{_fmt(res["Ncr_z_kN"],4)})','Risultato':_fmt(res['lambda_z'],4)},
        {'Parametro':'αz [-]','Formula':'coefficiente curva di instabilità','Sostituzione':f'curva {inp.curve_z}','Risultato':_fmt(res['alpha_z'],4)},
        {'Parametro':'φz [-]','Formula':'φ = 0.5 [1 + α(λ̄-0.2) + λ̄²]','Sostituzione':f'0.5·[1 + {res["alpha_z"]:.4f}·({_fmt(res["lambda_z"],4)}-0.2) + {_fmt(res["lambda_z"],4)}²]','Risultato':_fmt(phi_z,4)},
        {'Parametro':'χz [-]','Formula':'χ = 1 / [φ + √(φ² - λ̄²)]','Sostituzione':'-','Risultato':_fmt(res['chi_z'],4)},
        {'Parametro':'Nb,z,Rd [kN]','Formula':'Nb,Rd = χ · Aeff · fy / γM1','Sostituzione':f'{_fmt(res["chi_z"],4)}·Aeff·fy/{_fmt(inp.gamma_M1,2)}','Risultato':_fmt(res['Nb_z_Rd_kN'],4)},
    ]
    return pd.DataFrame(lines)


def ltb_table(inp: InputElemento, res: Dict[str,float]) -> pd.DataFrame:
    lines = [
        {'Parametro':'k [-]','Formula':'coefficiente di lunghezza efficace LTB','Sostituzione':'input/preset utente','Risultato':_fmt(inp.k_factor,4)},
        {'Parametro':'kw [-]','Formula':'coefficiente di ingobbamento','Sostituzione':'input/preset utente','Risultato':_fmt(inp.kw_factor,4)},
        {'Parametro':'C1 [-]','Formula':'coefficiente del diagramma dei momenti','Sostituzione':'input/preset utente','Risultato':_fmt(inp.C1,4)},
        {'Parametro':'Mcr [kNm]','Formula':'Mcr = C1·π²·E·Iz/(kL)² · √[(GIt + π²EIw/(kwL)²)/(EIz)]','Sostituzione':'formula implementata nel codice','Risultato':_fmt(res['Mcr_kNm'],4)},
        {'Parametro':'λLT [-]','Formula':'λLT = √(Mref / Mcr)','Sostituzione':'Mref = Mcy,Rd·γM0/γM1','Risultato':_fmt(res['lambda_lt'],4)},
        {'Parametro':'αLT [-]','Formula':'coefficiente curva di svergolamento','Sostituzione':'curva a/c in funzione della famiglia','Risultato':_fmt(res['alpha_lt'],4)},
        {'Parametro':'χLT [-]','Formula':'χLT = 1 / [φ + √(φ² - λLT²)]','Sostituzione':'stessa struttura della verifica di instabilità','Risultato':_fmt(res['chi_lt'],4)},
        {'Parametro':'Mb,Rd [kNm]','Formula':'Mb,Rd = χLT · Mref','Sostituzione':'-','Risultato':_fmt(res['Mb_Rd_kNm'],4)},
    ]
    return pd.DataFrame(lines)


def interaction_table(inp: InputElemento, res: Dict[str,float], checks: Dict[str,float]) -> pd.DataFrame:
    lines = [
        {'Parametro':'ηN,sez [-]','Formula':'η = NEd / Npl,Rd','Sostituzione':f'{_fmt(max(inp.NEd_kN,0.0),3)}/{_fmt(res["Npl_Rd_kN"],4)}','Risultato':_fmt(checks['eta_Nsec'],4)},
        {'Parametro':'ηN,inst [-]','Formula':'η = max(NEd/Nb,y,Rd ; NEd/Nb,z,Rd)','Sostituzione':'-','Risultato':_fmt(checks['eta_Nbuck'],4)},
        {'Parametro':'MNy [kNm]','Formula':'momento resistente ridotto per N, asse y','Sostituzione':'formula semplificata implementata per sezioni I classe 1-2','Risultato':_fmt(checks['MNy_kNm'],4)},
        {'Parametro':'MNz [kNm]','Formula':'momento resistente ridotto per N, asse z','Sostituzione':'formula semplificata implementata per sezioni I classe 1-2','Risultato':_fmt(checks['MNz_kNm'],4)},
        {'Parametro':'a_red [-]','Formula':'a = min[(Aeff - 2btf)/Aeff ; 0.5]','Sostituzione':'-','Risultato':_fmt(checks['a_red'],4)},
        {'Parametro':'β [-]','Formula':'β = min(5n ; 1)','Sostituzione':'n = NEd/Npl,Rd','Risultato':_fmt(checks['beta'],4)},
        {'Parametro':'ηsec [-]','Formula':'sez. I cls 1-2: (N/Npl,Rd)^2 + (My/MNy)^β + (Mz/MNz)^β; altrimenti N/Npl,Rd + My/Mcy,Rd + Mz/Mcz,Rd','Sostituzione':'-','Risultato':_fmt(checks['eta_sec'],4)},
        {'Parametro':'μy [-]','Formula':'coeff. di interazione asse y','Sostituzione':'formula implementata nel codice','Risultato':_fmt(checks['mu_y'],4)},
        {'Parametro':'μz [-]','Formula':'coeff. di interazione asse z','Sostituzione':'formula implementata nel codice','Risultato':_fmt(checks['mu_z'],4)},
        {'Parametro':'ky [-]','Formula':'ky = max[1 - μy·NEd/(Nb,y,Rd/γM1) ; 0.2]','Sostituzione':'-','Risultato':_fmt(checks['ky'],4)},
        {'Parametro':'kz [-]','Formula':'kz = max[1 - μz·NEd/(Nb,z,Rd/γM1) ; 0.2]','Sostituzione':'-','Risultato':_fmt(checks['kz'],4)},
        {'Parametro':'ηinst [-]','Formula':'η = N/Nb,min,Rd + ky·My/Mcy,Rd + kz·Mz/Mcz,Rd','Sostituzione':'-','Risultato':_fmt(checks['eta_inst'],4)},
        {'Parametro':'μLT [-]','Formula':'μLT = min(0.15·λLT - 0.15 ; 0.9)','Sostituzione':'-','Risultato':_fmt(checks['mu_lt'],4)},
        {'Parametro':'kLT [-]','Formula':'kLT = max[1 - μLT·NEd/(Nb,z,Rd/γM1) ; 0.2]','Sostituzione':'-','Risultato':_fmt(checks['klt'],4)},
        {'Parametro':'ηLT [-]','Formula':'η = N/Nb,z,Rd + kLT·My/Mb,Rd + kz·Mz/Mcz,Rd','Sostituzione':'-','Risultato':_fmt(checks['eta_ltb'],4)},
    ]
    return pd.DataFrame(lines)


def summary_dataframe(row: pd.Series, inp: InputElemento, classes: Dict[str,int], eff: Dict[str,float], res: Dict[str,float], checks: Dict[str,float]) -> pd.DataFrame:
    rows = [
        ('Profilo', row['Denominazione']), ('Famiglia', row['Categoria']), ('Norma', row['Norma']), ('A lorda [cm²]', row['Area_A_cm2']), ('A efficace [cm²]', eff['Aeff_cm2']), ('Peso [kg/m]', row['Peso_P_kg_m']),
        ('Jx [cm⁴]', row['Inerzia_Jx_cm4']), ('Jy [cm⁴]', row['Inerzia_Jy_cm4']), ('Wel,x [cm³]', row['Wel_x_cm3']), ('Wel,y [cm³]', row['Wel_y_cm3']), ('Weff,x [cm³]', eff['Weff_y_cm3']), ('Weff,y [cm³]', eff['Weff_z_cm3']),
        ('Classe compressione [-]', classes['compressione']), ('Classe flessione [-]', classes['flessione']), ('Classe pressoflessione [-]', classes['pressoflessione']), ('ρ flange [-]', eff['rho_flange']), ('ρ web comp. [-]', eff['rho_web_comp']), ('ρ web fless. [-]', eff['rho_web_bend']),
        ('Npl,Rd [kN]', res['Npl_Rd_kN']), ('Nb,y,Rd [kN]', res['Nb_y_Rd_kN']), ('Nb,z,Rd [kN]', res['Nb_z_Rd_kN']), ('Mcy,Rd [kNm]', res['Mcy_Rd_kNm']), ('Mcz,Rd [kNm]', res['Mcz_Rd_kNm']), ('Mcr [kNm]', res['Mcr_kNm']), ('Mb,Rd [kNm]', res['Mb_Rd_kNm']),
        ('χy [-]', res['chi_y']), ('χz [-]', res['chi_z']), ('χLT [-]', res['chi_lt']), ('η N sezione [-]', checks['eta_Nsec']), ('η N instabilità [-]', checks['eta_Nbuck']), ('η pressoflessione sezione [-]', checks['eta_sec']), ('η instabilità flessione+compressione [-]', checks['eta_inst']), ('η svergolamento / flesso-torsione [-]', checks['eta_ltb']),
    ]
    return pd.DataFrame(rows, columns=['Parametro', 'Valore'])


def notes(row: pd.Series, classes: Dict[str,int], eff: Dict[str,float], checks: Dict[str,float]) -> List[str]:
    out = []
    if classes['pressoflessione'] == 4:
        out.append('È stata attivata una sezione efficace di classe 4 con riduzione distinta di flange e anima per la verifica dell’elemento.')
    if checks['eta_inst'] > checks['eta_sec'] and checks['eta_inst'] >= max(checks['eta_Nbuck'], checks['eta_ltb'] if not pd.isna(checks['eta_ltb']) else -1):
        out.append('La verifica governante è l’instabilità per flessione e compressione assiale.')
    if not pd.isna(checks['eta_ltb']) and checks['eta_ltb'] >= max(checks['eta_inst'], checks['eta_sec']):
        out.append('La verifica governante è lo svergolamento / instabilità flesso-torsionale.')
    if checks['eta_Nbuck'] >= max(checks['eta_sec'], checks['eta_inst']) and checks['eta_Nbuck'] >= (checks['eta_ltb'] if not pd.isna(checks['eta_ltb']) else -1):
        out.append('La verifica governante è la forza normale con instabilità della membratura.')
    if family_shape(row['SheetName']) not in {'I','U','L'}:
        out.append('Per le sezioni cave e per alcune famiglie speciali il modello di svergolamento è meno significativo; la parte principale della verifica rimane forza normale / pressoflessione / instabilità.')
    return out


def section_polygons(row: pd.Series) -> List[np.ndarray]:
    shape = family_shape(row['SheetName']); h = float(row['Altezza_h_mm']); b = float(row['Base_b_mm']); tw = float(row['Spessore_anima_tw_mm']); tf = float(row['Spessore_ala_tf_mm']) if not pd.isna(row['Spessore_ala_tf_mm']) else tw
    polys = []
    if shape == 'I':
        y0 = -h/2
        polys.append(np.array([[-b/2,y0], [b/2,y0], [b/2,y0+tf], [-b/2,y0+tf], [-b/2,y0]]))
        polys.append(np.array([[-tw/2,y0+tf], [tw/2,y0+tf], [tw/2,h/2-tf], [-tw/2,h/2-tf], [-tw/2,y0+tf]]))
        polys.append(np.array([[-b/2,h/2-tf], [b/2,h/2-tf], [b/2,h/2], [-b/2,h/2], [-b/2,h/2-tf]]))
    elif shape == 'U':
        x0 = -b/2; y0 = -h/2
        polys.append(np.array([[x0,y0],[x0+tw,y0],[x0+tw,h/2],[x0,h/2],[x0,y0]]))
        polys.append(np.array([[x0,y0],[x0+b,y0],[x0+b,y0+tf],[x0,y0+tf],[x0,y0]]))
        polys.append(np.array([[x0,h/2-tf],[x0+b,h/2-tf],[x0+b,h/2],[x0,h/2],[x0,h/2-tf]]))
    elif shape == 'L':
        t = tw; x0, y0 = -b/2, -h/2
        polys.append(np.array([[x0,y0],[x0+b,y0],[x0+b,y0+t],[x0+t,y0+t],[x0+t,y0+h],[x0,y0+h],[x0,y0]]))
    elif shape in {'RHS','SHS'}:
        t = tw; x0, y0 = -b/2, -h/2
        outer = np.array([[x0,y0],[x0+b,y0],[x0+b,y0+h],[x0,y0+h],[x0,y0]])
        inner = np.array([[x0+t,y0+t],[x0+b-t,y0+t],[x0+b-t,y0+h-t],[x0+t,y0+h-t],[x0+t,y0+t]])
        polys.extend([outer, inner])
    elif shape == 'CHS':
        r = h/2; ang = np.linspace(0, 2*np.pi, 100)
        outer = np.column_stack([r*np.cos(ang), r*np.sin(ang)])
        ri = max(r - tw, 0.1); inner = np.column_stack([ri*np.cos(ang), ri*np.sin(ang)])
        polys.extend([outer, inner])
    else:
        x0, y0 = -b/2, -h/2; polys.append(np.array([[x0,y0],[x0+b,y0],[x0+b,y0+h],[x0,y0+h],[x0,y0]]))
    return polys


def figura_sezione_2d(row: pd.Series) -> go.Figure:
    shape = family_shape(row['SheetName']); fig = go.Figure(); polys = section_polygons(row)
    for i, poly in enumerate(polys):
        fill = 'toself' if not (shape in {'RHS','SHS','CHS'} and i == 1) else 'none'
        fig.add_trace(go.Scatter(x=poly[:,0], y=poly[:,1], mode='lines', fill=fill, line=dict(color='black', width=2), fillcolor='rgba(70,130,180,0.35)', showlegend=False))
    fig.add_hline(y=0, line_dash='dot', line_color='gray'); fig.add_vline(x=0, line_dash='dot', line_color='gray')
    fig.update_layout(title='Sezione del profilo', xaxis_title='z [mm]', yaxis_title='y [mm]', template='plotly_white', height=420, margin=dict(l=20,r=20,t=50,b=20))
    fig.update_yaxes(scaleanchor='x', scaleratio=1)
    return fig


def figura_sezione_3d(row: pd.Series, length_m: float = 1.0) -> go.Figure:
    # Horizontal beam development along X axis
    L = length_m * 1000.0
    fig = go.Figure()
    for poly in section_polygons(row):
        z = poly[:,0]; y = poly[:,1]
        x0 = np.zeros_like(z); x1 = np.full_like(z, L)
        fig.add_trace(go.Scatter3d(x=x0, y=y, z=z, mode='lines', line=dict(color='dimgray', width=6), showlegend=False))
        fig.add_trace(go.Scatter3d(x=x1, y=y, z=z, mode='lines', line=dict(color='black', width=6), showlegend=False))
        for i in np.linspace(0, len(z)-1, min(18, len(z)), dtype=int):
            fig.add_trace(go.Scatter3d(x=[0,L], y=[y[i],y[i]], z=[z[i],z[i]], mode='lines', line=dict(color='gray', width=3), showlegend=False))
    fig.update_layout(title='Sviluppo 3D della trave (orizzontale)', template='plotly_white', height=360,
                      scene=dict(xaxis_title='lunghezza barra [mm]', yaxis_title='y [mm]', zaxis_title='z [mm]', aspectratio=dict(x=4.5,y=1,z=1), camera=dict(eye=dict(x=1.8,y=0.55,z=0.35))),
                      margin=dict(l=0,r=0,t=50,b=0))
    return fig


# --- FUNZIONI LTBEAM STYLE (Integrate e spacchettate dalla v1.5) ---

def _segmentized_lengths(L: float, restraints: List[dict]) -> List[tuple]:
    pts = [0.0, float(L)]
    for r in restraints:
        if r['type'] in {'v and θ fixed', 'v fixed'} and 0 < r['x'] < L:
            pts.append(float(r['x']))
    pts = sorted(set(pts))
    return [(pts[i], pts[i+1]) for i in range(len(pts)-1)]


def _restraint_bonus(r: dict, h: float) -> float:
    if r['type'] == 'v and θ fixed':
        return 1.35
    if r['type'] == 'v fixed':
        return 1.10 * (1 + 0.15 * abs(r['z']) / max(h, 1e-9))
    if r['type'] == 'θ fixed':
        return 1.12
    if r['type'] == 'Elastic springs':
        return min(1.0 + 0.015 * max(r.get('Rv', 0), 0) + 0.004 * max(r.get('Rq', 0), 0), 1.6)
    return 1.0


def _moment_hinged(L: float, M1: float, M2: float, q1: float, q2: float, pts: List[dict], n: int = 401):
    x = np.linspace(0.0, L, n)
    Wq = (q1 + q2) * L / 2.0
    Mx_q = L**2 * (q1 / 6.0 + q2 / 3.0)
    Wp = sum(p['F'] for p in pts)
    Mx_p = sum(p['F'] * p['x'] for p in pts)
    RB = -(M1 + M2 + Mx_q + Mx_p) / L
    RA = -(Wq + Wp) - RB
    m = M1 + RA * x + q1 * x**2 / 2.0 + (q2 - q1) * x**3 / (6.0 * L)
    v = RA + q1 * x + (q2 - q1) * x**2 / (2.0 * L)
    for p in pts:
        mask = x >= p['x']
        m[mask] += p['F'] * (x[mask] - p['x'])
        v[mask] += p['F']
    return x, m, v


def _moment_cantilever(L: float, M2: float, q1: float, q2: float, pts: List[dict], n: int = 401):
    x = np.linspace(0.0, L, n)
    m = np.full_like(x, float(M2))
    v = np.zeros_like(x)
    for i, xi in enumerate(x):
        xx = np.linspace(xi, L, 60)
        qq = q1 + (q2 - q1) * xx / L
        m[i] += np.trapz(qq * (xx - xi), xx)
        v[i] += np.trapz(qq, xx)
        for p in pts:
            if p['x'] >= xi:
                m[i] += p['F'] * (p['x'] - xi)
                v[i] += p['F']
    return x, m, v


def ltbeam_style_analysis(row: pd.Series, L_m: float, end_preset: str, inplane_support: str, M1_kNm: float, M2_kNm: float, q1_kNm: float, q2_kNm: float, points: List[dict], restraints: List[dict], N: int = 100) -> dict:
    L = L_m * 1000.0
    h = float(row['Altezza_h_mm'])
    Iz = float(row['Inerzia_Jy_cm4']) * 1e4
    It = max(float(row['Inerzia_It_cm4']) * 1e4 if not pd.isna(row['Inerzia_It_cm4']) else 0.0, 1e2)
    Iw = max(float(row['Ingobbamento_Iw_cm6']) * 1e6 if not pd.isna(row['Ingobbamento_Iw_cm6']) else 0.0, 1e3)
    k0 = LTB_END_PRESETS[end_preset]['k']
    kw0 = LTB_END_PRESETS[end_preset]['kw']
    
    pts = [{'x': float(p['xf']) * L, 'F': float(p['F'])} for p in points if p.get('enabled', False)]
    q1 = float(q1_kNm) / 1000.0
    q2 = float(q2_kNm) / 1000.0
    M1 = float(M1_kNm) * 1e6
    M2 = float(M2_kNm) * 1e6
    
    if inplane_support == 'Cantilever':
        x, m, v = _moment_cantilever(L, M2, q1, q2, pts, max(201, int(N) * 3))
    else:
        x, m, v = _moment_hinged(L, M1, M2, q1, q2, pts, max(201, int(N) * 3))
        
    Mmax = float(np.max(np.abs(m)) / 1e6)
    xmax = float(x[np.argmax(np.abs(m))] / L)
    
    rs = [{'x': float(r['xf']) * L, 'type': r['type'], 'z': float(r.get('z', 0)), 'Rv': float(r.get('Rv', 0)), 'Rq': float(r.get('Rq', 0))} for r in restraints if r['type'] != 'None']
    
    segs = []
    for a, b in _segmentized_lengths(L, rs):
        bonus = 1.0
        for r in rs:
            if abs(r['x'] - a) < 1e-6 or abs(r['x'] - b) < 1e-6:
                bonus = max(bonus, _restraint_bonus(r, h))
        Li = b - a
        term = G_MODULUS * It + (math.pi**2 * E_MODULUS * Iw) / max((kw0 * Li)**2, 1e-9)
        Mcr = math.pi**2 * E_MODULUS * Iz / max((k0 * Li)**2, 1e-9) * math.sqrt(max(term / (E_MODULUS * Iz), 1e-12)) * bonus / 1e6
        segs.append({'a_mm': a, 'b_mm': b, 'Lseg_mm': Li, 'bonus': bonus, 'Mcr_seg_kNm': Mcr})
        
    Mcr = min(s['Mcr_seg_kNm'] for s in segs) if segs else np.nan
    mu = Mcr / max(Mmax, 1e-9)
    
    summary_df = pd.DataFrame([
        ('L [m]', L_m), 
        ('N elementi', int(N)), 
        ('Preset vincoli LTB', end_preset), 
        ('Supporti nel piano di flessione', inplane_support), 
        ('Iz [cm4]', float(row['Inerzia_Jy_cm4'])), 
        ('It [cm4]', float(row['Inerzia_It_cm4']) if not pd.isna(row['Inerzia_It_cm4']) else np.nan), 
        ('Iw [cm6]', float(row['Ingobbamento_Iw_cm6']) if not pd.isna(row['Ingobbamento_Iw_cm6']) else np.nan), 
        ('Mmax [kNm]', Mmax), 
        ('x/L di Mmax [-]', xmax), 
        ('μ = Mcr/Mmax [-]', mu), 
        ('Mcr [kNm]', Mcr)
    ], columns=['Parametro', 'Valore'])
    
    return {
        'x_mm': x, 
        'M_kNm': m / 1e6, 
        'V_kN': v / 1000.0, 
        'Mmax_kNm': Mmax, 
        'xmax_rel': xmax, 
        'mu': mu, 
        'Mcr_kNm': Mcr, 
        'segments': pd.DataFrame(segs), 
        'summary': summary_df
    }


def ltbeam_input_table(points: List[dict], restraints: List[dict], end_preset: str, inplane_support: str, N: int) -> pd.DataFrame:
    rows = [
        ('Preset vincoli LTB', end_preset), 
        ('Supporti nel piano di flessione', inplane_support), 
        ('Numero elementi N', N)
    ]
    for i, p in enumerate(points, 1):
        if p.get('enabled', False):
            rows += [(f'P{i} - F [kN]', p['F']), (f'P{i} - xf [-]', p['xf'])]
    for i, r in enumerate(restraints, 1):
        if r['type'] != 'None':
            rows += [(f'R{i} - tipo', r['type']), (f'R{i} - xf [-]', r['xf']), (f'R{i} - z [mm]', r['z']), (f'R{i} - Rv', r['Rv']), (f'R{i} - Rq', r['Rq'])]
    return pd.DataFrame(rows, columns=['Parametro', 'Valore'])


def ltbeam_results_table(res: dict) -> pd.DataFrame:
    return res['summary']


def ltbeam_diagram_figure(res: dict) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=res['x_mm'] / 1000.0, y=res['M_kNm'], name='M [kNm]', line=dict(color='firebrick')))
    fig.add_trace(go.Scatter(x=res['x_mm'] / 1000.0, y=res['V_kN'], name='V [kN]', line=dict(color='royalblue'), yaxis='y2'))
    fig.update_layout(
        template='plotly_white', 
        height=320, 
        title='Diagrammi LTBeam-style: M(x) e V(x)', 
        xaxis_title='x [m]', 
        yaxis=dict(title='M [kNm]'), 
        yaxis2=dict(title='V [kN]', overlaying='y', side='right')
    )
    return fig


def ltbeam_eigenmode_placeholder(res: dict) -> go.Figure:
    x = np.array(res['x_mm']) / 1000.0
    L = max(x.max(), 1e-9)
    v = np.sin(np.pi * x / L)
    th = np.sin(2 * np.pi * x / L)
    vp = np.cos(np.pi * x / L)
    thp = np.cos(2 * np.pi * x / L)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=v, name='v'))
    fig.add_trace(go.Scatter(x=x, y=th, name='θ'))
    fig.add_trace(go.Scatter(x=x, y=vp, name="v'"))
    fig.add_trace(go.Scatter(x=x, y=thp, name="θ'"))
    fig.update_layout(
        template='plotly_white', 
        height=280, 
        title='Eigenmode LTBeam-style (shape qualitativa)', 
        xaxis_title='x [m]'
    )
    return fig