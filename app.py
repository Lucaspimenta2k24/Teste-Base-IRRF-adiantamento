import os
import re
import pandas as pd
import pdfplumber
import streamlit as st

def extrair_dados_extrato(caminho_pdf, codigo_rubrica_irrf="999", competencia=""):
    dados_funcionarios = []
    
    # Expressões regulares ajustadas para maior flexibilidade
    padrao_cabecalho_emp = re.compile(r"Empr\.:?\s*(\d+)\s+(.*?)\s+Situação:?\s*(.*?)\s+CPF:?\s*([\d\.\-]+)", re.IGNORECASE)
    padrao_base_irrf = re.compile(r"Base\s*IRRF:?\s*([\d\.,]+)", re.IGNORECASE)
    padrao_rubrica = re.compile(rf"\b({codigo_rubrica_irrf})\b\s+(.*?)\s+([\d\.,]+)\s+([\d\.,]+)\s*([DP])", re.IGNORECASE)

    with pdfplumber.open(caminho_pdf) as pdf:
        texto_completo = ""
        for pagina in pdf.pages:
            texto_extraido = pagina.extract_text()
            if texto_extraido:
                texto_completo += texto_extraido + "\n"

    # Se quiser inspecionar o texto bruto que o PDF gerou, descomente a linha abaixo:
    # st.text_area("Texto Extraído do PDF (Debug):", texto_completo[:2000])

    # Dividir o texto por blocos de funcionários (tentando variações comuns)
    blocos = re.split(r"Empr\.:?", texto_completo, flags=re.IGNORECASE)
    
    for bloco in blocos[1:]:
        linhas = bloco.split("\n")
        primeira_linha = linhas[0]
        
        match_emp = padrao_cabecalho_emp.search("Empr.: " + primeira_linha)
        if not match_emp:
            continue
            
        emp_id, nome, situacao, cpf = match_emp.groups()
        bloco_texto = "\n".join(linhas)
        
        # Extrair Base IRRF
        match_base = padrao_base_irrf.search(bloco_texto)
        base_irrf = match_base.group(1) if match_base else "0,00"
        
        # Extrair valor do IRRF com base na rubrica informada
        valor_irrf = "0,00"
        matches_rubrica = padrao_rubrica.findall(bloco_texto)
        for rubrica, desc, alq, valor, tipo in matches_rubrica:
            if rubrica == str(codigo_rubrica_irrf):
                valor_irrf = valor
                break

        dados_funcionarios.append({
            "Empresa/ID": emp_id.strip(),
            "Funcionário": nome.strip(),
            "CPF": cpf.strip(),
            "Competência": competencia.strip(),
            "Base IRRF": base_irrf,
            f"IRRF (Rubrica {codigo_rubrica_irrf})": valor_irrf
        })

    return pd.DataFrame(dados_funcionarios)

# --- Interface Gráfica com Streamlit ---
st.title("Extrator Automatizado de IRRF e Geração de Arquivos")
st.write("Faça o upload dos extratos em PDF, informe a competência e configure os parâmetros de rubrica.")

col1, col2 = st.columns(2)
with col1:
    codigo_rubrica = st.text_input("Código da Rubrica para IRRF:", value="999")
with col2:
    competencia_input = st.text_input("Competência (Ex: 09/2026):", value="09/2026")

arquivos_pdf = st.file_uploader("Selecione os arquivos PDF", type=["pdf"], accept_multiple_files=True)

if arquivos_pdf and st.button("Processar Extratos e Gerar Arquivos"):
    todos_dados = []
    
    for arquivo in arquivos_pdf:
        caminho_temp = os.path.join("temp", arquivo.name)
        os.makedirs("temp", exist_ok=True)
        with open(caminho_temp, "wb") as f:
            f.write(arquivo.getbuffer())
            
        df_extrato = extrair_dados_extrato(caminho_temp, codigo_rubrica, competencia_input)
        df_extrato["Arquivo Origem"] = arquivo.name
        todos_dados.append(df_extrato)
        
        os.remove(caminho_temp)
        
    if todos_dados:
        df_final = pd.concat(todos_dados, ignore_index=True)
        
        if df_final.empty:
            st.warning("Nenhum dado foi extraído. Verifique se o **Código da Rubrica** informado confere com o do PDF ou se o layout do PDF é compatível.")
        else:
            st.success("Processamento concluído com sucesso!")
            st.dataframe(df_final)
            
            # Geração Excel (Agora com openpyxl instalado funcionará)
            output_excel = "extrato_irrf_consolidado.xlsx"
            df_final.to_excel(output_excel, index=False)
            
            # Geração TXT
            output_txt = "importacao_irrf.txt"
            with open(output_txt, "w", encoding="utf-8") as f:
                for _, row in df_final.iterrows():
                    linha_txt = f"{row['Empresa/ID']};{row['CPF']};{row['Competência']};{row['Base IRRF']};{row[f'IRRF (Rubrica {codigo_rubrica})']}\n"
                    f.write(linha_txt)

            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                with open(output_excel, "rb") as f:
                    st.download_button(
                        label="Baixar Planilha Consolidada (Excel)",
                        data=f,
                        file_name=output_excel,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
            with col_dl2:
                with open(output_txt, "r", encoding="utf-8`") as f:
                    st.download_button(
                        label="Baixar TXT para Importação",
                        data=f,
                        file_name=output_txt,
                        mime="text/plain"
                    )
