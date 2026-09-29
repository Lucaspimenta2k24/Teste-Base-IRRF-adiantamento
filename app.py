import os
import re
import pandas as pd
import pdfplumber
import streamlit as st

def converter_competencia_aaamm(competencia_str):
    """Converte MM/AAAA para AAAAMM conforme o leiaute."""
    comp_limpa = re.sub(r'\D', '', competencia_str)
    if '/' in competencia_str:
        partes = competencia_str.split('/')
        if len(partes) == 2:
            mes, ano = partes[0].zfill(2), partes[1]
            return f"{ano}{mes}"
    if len(comp_limpa) == 6:
        # Assume que o formato digitado pode ser MMAAAA
        mes = comp_limpa[:2]
        ano = comp_limpa[2:]
        return f"{ano}{mes}"
    return comp_limpa.zfill(6)[:6]

def extrair_dados_extrato(caminho_pdf, codigo_empresa="1", codigo_rubrica="999", competencia=""):
    """
    Extrai informações de funcionários (Código do Empregado, Nome, CPF e Base IRRF)
    de forma flexível a partir do PDF.
    """
    dados_funcionarios = []
    
    with pdfplumber.open(caminho_pdf) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_extraido = pagina.extract_text()
            if texto_extraido:
                texto_completo += texto_extraido + "\n"

    if not texto_completo.strip():
        return pd.DataFrame()

    # Expressões regulares para capturar dados
    padrao_cabecalho_emp = re.compile(r"Empr\.?:?\s*(\d+)\s+(.*?)\s+Situação:?\s*(.*?)\s+CPF:?\s*([\d\.\-]+)", re.IGNORECASE)
    padrao_cpf = re.compile(r"(\d{3}\.\d{3}\.\d{3}-\d{2})")
    padrao_base_irrf = re.compile(r"Base\s*IRRF:?\s*([\d\.,]+)", re.IGNORECASE)

    # Dividir o texto em blocos utilizando o CPF como âncora
    blocos = re.split(r"(?=\d{3}\.\d{3}\.\d{3}-\d{2})", texto_completo)
    
    for bloco in blocos:
        match_cpf = padrao_cpf.search(bloco)
        if not match_cpf:
            continue
            
        cpf = match_cpf.group(1)
        
        # Tentar extrair o ID do empregado e o nome do bloco
        match_emp = padrao_cabecalho_emp.search(bloco)
        if match_emp:
            emp_id = match_emp.group(1)
            nome = match_emp.group(2).strip()
        else:
            emp_id = "1" # Fallback caso não ache na âncora exata
            nome = "Funcionário"
            
        # Buscar a Base IRRF
        match_base = padrao_base_irrf.search(bloco)
        base_irrf = match_base.group(1) if match_base else "0,00"

        # Evitar duplicatas do mesmo CPF no mesmo arquivo
        if not any(d['CPF'] == cpf for d in dados_funcionarios):
            dados_funcionarios.append({
                "Empresa": str(codigo_empresa).strip(),
                "Código Empregado": str(emp_id).strip(),
                "Funcionário": nome,
                "Competência": competencia.strip(),
                "Base IRRF": base_irrf,
                "Código Rubrica": str(codigo_rubrica).strip()
            })

    return pd.DataFrame(dados_funcionarios)

def gerar_linha_posicional(row):
    """
    Gera a linha em formato posicional de acordo estrito com o leiaute fornecido:
    - 001-002 (2): Fixo "41"
    - 003-012 (10): Código do empregado ("0000000000")
    - 013-018 (6): Competência ("AAAAMM")
    - 019-027 (9): Código da rubrica ("000000000")
    - 028-029 (2): Tipo do Processo ("00")
    - 030-038 (9): Valor / Base IRRF ("000000000")
    - 039-048 (10): Empresa ("0000000000")
    """
    f_fixo = "41"
    f_emp = str(row['Código Empregado']).zfill(10)[:10]
    f_comp = converter_competencia_aaamm(row['Competência'])
    f_rubrica = str(row['Código Rubrica']).zfill(9)[:9]
    f_proc = "00"
    
    # Remove pontos e vírgulas do valor para ajustar ao formato numérico inteiro de 9 posições
    val_limpo = re.sub(r'[^\d]', '', str(row['Base IRRF']))
    f_valor = val_limpo.zfill(9)[:9]
    
    f_empresa = str(row['Empresa']).zfill(10)[:10]
    
    return f"{f_fixo}{f_emp}{f_comp}{f_rubrica}{f_proc}{f_valor}{f_empresa}\n"

# --- Interface Gráfica com Streamlit ---
st.title("Extrator de Base IRRF - Leiaute de Importação TXT")
st.write("Faça o upload dos extratos em PDF, configure os parâmetros e gere o arquivo TXT posicional.")

col1, col2, col3 = st.columns(3)
with col1:
    codigo_empresa_input = st.text_input("Código da Empresa:", value="1")
with col2:
    codigo_rubrica = st.text_input("Código da Rubrica (TXT):", value="999")
with col3:
    competencia_input = st.text_input("Competência (Ex: 09/2026):", value="09/2026")

arquivos_pdf = st.file_uploader("Selecione os arquivos PDF", type=["pdf"], accept_multiple_files=True)

if arquivos_pdf and st.button("Processar Extratos e Gerar Arquivos"):
    todos_dados = []
    
    for arquivo in arquivos_pdf:
        caminho_temp = os.path.join("temp", arquivo.name)
        os.makedirs("temp", exist_ok=True)
        with open(caminho_temp, "wb") as f:
            f.write(arquivo.getbuffer())
            
        df_extrato = extrair_dados_extrato(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
        df_extrato["Arquivo Origem"] = arquivo.name
        todos_dados.append(df_extrato)
        
        os.remove(caminho_temp)
        
    if todos_dados:
        df_final = pd.concat(todos_dados, ignore_index=True)
        
        if df_final.empty:
            st.warning("Nenhum dado foi extraído. Certifique-se de que os PDFs contêm os CPFs e o campo 'Base IRRF'.")
        else:
            st.success("Processamento concluído com sucesso!")
            st.dataframe(df_final)
            
            # Geração de Planilha CSV para conferência
            output_csv = "extrato_irrf_consolidado.csv"
            df_final.to_csv(output_csv, index=False, sep=";", encoding="utf-8-sig")
            
            # Geração do Arquivo TXT posicional estrito conforme o leiaute
            output_txt = "importacao_irrf.txt"
            with open(output_txt, "w", encoding="utf-8") as f:
                for _, row in df_final.iterrows():
                    linha_posicional = gerar_linha_posicional(row)
                    f.write(linha_posicional)

            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                with open(output_csv, "rb") as f:
                    st.download_button(
                        label="Baixar Planilha de Conferência (CSV)",
                        data=f,
                        file_name=output_csv,
                        mime="text/csv"
                    )
                    
            with col_dl2:
                with open(output_txt, "r", encoding="utf-8") as f:
                    st.download_button(
                        label="Baixar TXT Posicional (Leiaute)",
                        data=f,
                        file_name=output_txt,
                        mime="text/plain"
                    )
