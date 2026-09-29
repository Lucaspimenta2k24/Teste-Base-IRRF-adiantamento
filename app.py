import re
import pandas as pd
import pdfplumber
import streamlit as st

# Configuração da Página do Streamlit
st.set_page_config(
    page_title="Importador de Extrato para Domínio", page_icon="📄", layout="wide"
)

st.title("📊 Conversor de Extrato PDF para TXT (Leiaute Domínio)")
st.markdown(
    """
Este aplicativo lê os extratos mensais da folha em **PDF**, extrai o **Código do Empregado** e a **Base de IRRF**, 
e gera o arquivo **TXT** estruturado para importação no sistema Domínio (**Tipo 41 - Adiantamento**, **Rubrica 2000**).
"""
)

# Barra Lateral para Configurações
st.sidebar.header("⚙️ Parâmetros de Importação")
codigo_empresa = st.sidebar.text_input(
    "Código da Empresa", value="1", max_chars=10
)
data_lancamento = st.sidebar.text_input(
    "Data de Referência (MM/AAAA)", value="01/2026"
)

st.sidebar.markdown("---")
st.sidebar.info(
    "Dica: Caso o PDF da sua folha tenha um leiaute muito específico, você"
    " pode ajustar as expressões regulares (Regex) no código fonte da função de"
    " extração."
)

# Área de Upload de Arquivos PDF
uploaded_files = st.file_uploader(
    "Importar Extratos Mensais (PDF)",
    type=["pdf"],
    accept_multiple_files=True,
)


def extrair_dados_pdf(pdf_file):
  """Função responsável por ler o PDF e extrair o código do empregado e a base de IRRF.

  Utiliza expressões regulares para buscar padrões comuns em extratos de folha.
  """
  dados_extraidos = []

  with pdfplumber.open(pdf_file) as pdf:
    for page in pdf.pages:
      texto = page.extract_text()
      if not texto:
        continue

      linhas = texto.split("\n")
      codigo_empregado = None
      base_irrf = None

      for linha in linhas:
        # Procura pelo código do empregado (Ex: Código: 123, Matrícula: 45, etc.)
        match_emp = re.search(
            r"(?:C[oó]digo|Matr[ií]cula|Emp\.?):\s*(\d+)", linha, re.IGNORECASE
        )
        if match_emp:
          codigo_empregado = match_emp.group(1)

        # Procura pela Base de IRRF (Ex: Base IRRF: 1.500,00 ou BC IRRF 2.340,50)
        match_irrf = re.search(
            r"(?:Base\s*(?:de\s*)?IRRF|BC\s*IRRF|IRRF\s*Base)[:\s]*([\d\.,]+)",
            linha,
            re.IGNORECASE,
        )
        if match_irrf:
          base_irrf_str = match_irrf.group(1)
          try:
            # Converte formato monetário brasileiro para float
            base_irrf_limpo = (
                base_irrf_str.replace(".", "").replace(",", ".").strip()
            )
            base_irrf = float(base_irrf_limpo)
          except ValueError:
            pass

      # Se encontrou os dados na página, adiciona à lista
      if codigo_empregado and base_irrf is not None:
        dados_extraidos.append(
            {
                "Arquivo": pdf_file.name,
                "codigo_empregado": codigo_empregado,
                "base_irrf": base_irrf,
            }
        )

  return dados_extraidos


if uploaded_files:
  st.subheader("📁 Resumo dos Dados Extraídos")

  todos_dados = []

  for arquivo in uploaded_files:
    resultados = extrair_dados_pdf(arquivo)
    if resultados:
      todos_dados.extend(resultados)
    else:
      st.warning(
          f"Não foi possível extrair dados automaticamente do arquivo"
          f" {arquivo.name}. Verifique o leiaute do PDF."
      )

  if todos_dados:
    df = pd.DataFrame(todos_dados)

    # Exibe tabela prévia para conferência do usuário
    st.success(
        f"Leitura concluída com sucesso! Total de registros encontrados:"
        f" {len(df)}"
    )
    st.dataframe(df, use_container_width=True)

    st.markdown("---")

    # Botão para gerar e baixar o TXT
    if st.button("🚀 Gerar Arquivo TXT para Domínio"):
      linhas_txt = []

      for _, row in df.iterrows():
        cod_emp = codigo_empresa
        cod_emp_func = row["codigo_empregado"]
        val_irrf = row["base_irrf"]

        # Formatação do valor monetário com duas casas decimais e vírgula (ex: 1500,00)
        valor_formatado = f"{val_irrf:.2f}".replace(".", ",")

        # Padrão de Leiaute Domínio (Delimitado por ponto e vírgula):
        # Campos: Código Empresa; Código Empregado; Data; Tipo de Processo (41); Rubrica (2000); Valor
        linha = (
            f"{cod_emp};{cod_emp_func};{data_lancamento};41;2000;{valor_formatado}"
        )
        linhas_txt.append(linha)

      conteudo_txt = "\n".join(linhas_txt)

      # Botão de Download do arquivo gerado
      st.download_button(
          label="📥 Baixar Arquivo TXT (Pronto para Importação)",
          data=conteudo_txt,
          file_name="importacao_base_irrf_dominio.txt",
          mime="text/plain",
      )
  else:
    st.info(
        "Nenhum valor correspondente a 'Base IRRF' e 'Código do Empregado' foi"
        " identificado nos arquivos enviados."
    )
