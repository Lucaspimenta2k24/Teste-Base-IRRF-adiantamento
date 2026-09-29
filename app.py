import os
import re
import pandas as pd
import pdfplumber
import streamlit as st

def extrair_dados_extrato(caminho_pdf, codigo_empresa="1", codigo_rubrica="999", competencia=""):
    """
    Extrai informações de funcionários (buscando CPFs e Bases IRRF) de forma flexível,
    vinculando o código da empresa, da rubrica e a competência informados.
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

    # Expressões regulares flexíveis para localizar CPFs e Bases IRRF no texto
    padrao_cpf = re.compile(r"(\d{3}\.\d{3}\.\d{3}-\d{2})")
    padrao_base_irrf = re.compile(r"Base\s*IRRF:?\s*([\d\.,]+)", re.IGNORECASE)

    # Dividir o texto em blocos utilizando o CPF como âncora principal
    blocos = re.split(r"(?=\d{3}\.\d{3}\.\d{3}-\d{2})", texto_completo)
    
    for bloco in blocos:
        match_cpf = padrao_cpf.search(bloco)
        if not match_cpf:
            continue
            
        cpf = match_cpf.group(1)
        
        # Buscar a Base IRRF dentro deste bloco do funcionário
        match_base = padrao_base_irrf.search(bloco)
        base_irrf = match_base.group(1) if match_base else "0,00"
        
        # Tentar extrair o nome da primeira linha do bloco
        linhas = [l.strip() for l in bloco.split("\n") if l.strip()]
        nome = "Funcionário"
        if linhas:
            primeira_linha = linhas[0]
            # Remove termos comuns de cabeçalho para isolar o nome se possível
            nome_limpo = re.sub(r"(Empr\.?:?.*|Situação:?.*|CPF:?.*|Adm:?.*)", "", primeira_linha, flags=re.IGNORECASE).strip()
            if len(nome_limpo) > 2:
                nome = nome_limpo

        # Evitar duplicatas do mesmo CPF no mesmo arquivo
        if not any(d['CPF'] == cpf for d in dados_funcionarios):
            dados_funcionarios.append({
                "Empresa": str(codigo_empresa).strip(),
                "Funcionário": nome,
                "CPF": cpf,
                "Competência": competencia.strip(),
                "Base IRRF": base_irrf,
                "Código Rubrica": str(codigo_rubrica).strip()
            })

    return pd.DataFrame(dados_funcionarios)

# --- Interface Gráfica com Streamlit ---
st.title("Extrator Automatizado de Base IRRF e Geração de TXT")
st.write("Faça o upload dos extratos em PDF, configure os parâmetros abaixo e gere os arquivos de importação.")

# Campos de Parâmetros na Tela
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
            
            # Geração de Planilha (Excel/CSV)
            output_csv = "extrato_irrf_consolidado.csv"
            df_final.to_csv(output_csv, index=False, sep=";", encoding="utf-8-sig")
            
            # Geração do Arquivo TXT formatado com Empresa, CPF, Competência, Rubrica e Base IRRF
            output_txt = "importacao_irrf.txt"
            with open(output_txt, "w", encoding="utf-8") as f:
                for _, row in df_final.iterrows():
                    # Formato da linha do TXT: Cod_Empresa; CPF; Competencia; Cod_Rubrica; Base_IRRF
                    linha_txt = f"{row['Empresa']};{row['CPF']};{row['Competência']};{row['Código Rubrica']};{row['Base IRRF']}\n"
                    f.write(linha_txt)

            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                with open(output_csv, "rb") as f:
                    st.download_button(
                        label="Baixar Planilha Consolidada (CSV)",
                        data=f,
                        file_name=output_csv,
                        mime="text/csv"
                    )
                    
            with col_dl2:
                with open(output_txt, "r", encoding="utf-8") as f:
                    st.download_button(
                        label="Baixar TXT para Importação",
                        data=f,
                        file_name=output_txt,
                        mime="text/plain"
                    )
