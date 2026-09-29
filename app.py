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
        mes = comp_limpa[:2]
        ano = comp_limpa[2:]
        return f"{ano}{mes}"
    return comp_limpa.zfill(6)[:6]

def extrair_dados_extrato(caminho_pdf, codigo_empresa="1", codigo_rubrica="999", competencia=""):
    """
    Extrai os dados de cada funcionário garantindo flexibilidade na leitura da Base IRRF.
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

    # Identificar cada início de cadastro de funcionário pelo padrão do código da empresa/empregado
    partes_texto = re.split(r"(?=Empr\.?:?\s*\d+)", texto_completo, flags=re.IGNORECASE)
    
    padrao_emp = re.compile(r"Empr\.?:?\s*(\d+)", re.IGNORECASE)
    padrao_cpf = re.compile(r"(\d{3}\.\d{3}\.\d{3}-\d{2})")
    
    # Regex aprimorada para capturar variações e possíveis quebras de linha entre o rótulo e o valor da Base IRRF
    padrao_base_irrf = re.compile(
        r"(?:Base\s*(?:de\s*Cálculo\s*)?(?:do\s*)?IRRF|Base\s*Calc\.?\s*IRRF|IRRF\s*Base)[:\s\n]*([\d\.]+,\d{2})", 
        re.IGNORECASE
    )

    for bloco in partes_texto:
        if not bloco.strip():
            continue
            
        match_emp = padrao_emp.search(bloco)
        match_cpf = padrao_cpf.search(bloco)
        
        if not match_emp or not match_cpf:
            continue
            
        emp_id = match_emp.group(1).strip()
        cpf = match_cpf.group(1).strip()
        
        # Extração flexível da Base IRRF dentro do bloco isolado do funcionário
        match_base = padrao_base_irrf.search(bloco)
        base_irrf = match_base.group(1).strip() if match_base else "0,00"
        
        # Extrair o nome do funcionário
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        nome = "Funcionário"
        for linha in linhas:
            if "Empr" in linha or "Empresa" in linha:
                txt_limpo = re.sub(r"Empr\.?:?\s*\d+", "", linha, flags=re.IGNORECASE).strip()
                if len(txt_limpo) > 2:
                    nome = txt_limpo
                    break

        # Evitar duplicatas do mesmo funcionário/CPF
        if not any(d.get('CPF') == cpf and d.get('Código Empregado') == emp_id for d in dados_funcionarios):
            dados_funcionarios.append({
                "Empresa": str(codigo_empresa).strip(),
                "Código Empregado": emp_id,
                "Funcionário": nome,
                "CPF": cpf,
                "Competência": competencia.strip(),
                "Base IRRF": base_irrf,
                "Código Rubrica": str(codigo_rubrica).strip()
            })

    return pd.DataFrame(dados_funcionarios)

def gerar_linha_posicional(row):
    """
    Gera a linha em formato posicional de acordo com o leiaute.
    """
    f_fixo = "41"
    f_emp = str(row['Código Empregado']).zfill(10)[:10]
    f_comp = converter_competencia_aaamm(row['Competência'])
    f_rubrica = str(row['Código Rubrica']).zfill(9)[:9]
    f_proc = "00"
    
    # Remove pontos e vírgulas da base IRRF para formar o inteiro de 9 posições
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
    codigo_rubrica = st.text_input("Código da Rubrica (TXT):", value="2000")
with col3:
    competencia_input = st.text_input("Competência (Ex: 06/2026):", value="06/2026")

arquivos_pdf = st.file_uploader("Selecione os arquivos PDF", type=["pdf"], accept_multiple_files=True)

if arquivos_pdf and st.button("Processar Extratos e Gerar Arquivos"):
    todos_dados = []
    
    for arquivo in arquivos_pdf:
        caminho_temp = os.path.join("temp", arquivo.name)
        os.makedirs("temp", exist_ok=True)
        with open(caminho_temp, "wb") as f:
            f.write(arquivo.getbuffer())
            
        df_extrato = extrair_dados_extrato(caminho_temp, codigo_empresa_input, codigo_rubrica, competencia_input)
        if not df_extrato.empty:
            df_extrato["Arquivo Origem"] = arquivo.name
            todos_dados.append(df_extrato)
        
        os.remove(caminho_temp)
        
    if todos_dados:
        df_final = pd.concat(todos_dados, ignore_index=True)
        
        if df_final.empty:
            st.warning("Nenhum dado foi extraído. Verifique se o PDF contém os CPFs e o campo 'Base IRRF'.")
        else:
            st.success("Processamento concluído com sucesso!")
            st.dataframe(df_final)
            
            # Geração de Planilha CSV para conferência
            output_csv = "extrato_irrf_consolidado.csv"
            df_final.to_csv(output_csv, index=False, sep=";", encoding="utf-8-sig")
            
            # Geração do Arquivo TXT posicional estrito
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
    else:
        st.warning("Nenhum dado válido foi encontrado nos arquivos enviados.")
