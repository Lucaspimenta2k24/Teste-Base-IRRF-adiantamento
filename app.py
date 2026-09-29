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
modo_debug = st.sidebar.checkbox(
    "🛠️ Ativar Modo Debug (Exibir texto bruto do PDF)"
)

# Área de Upload de Arquivos PDF
uploaded_files = st.file_uploader(
    "Importar Extratos Mensais (PDF)",
    type=["pdf"],
    accept_multiple_files=True,
)


def extrair_dados_pdf(pdf_file, debug=False):
  """Função robusta para extração de código de empregado e base IRRF do PDF."""
  dados_extraidos = []
  texto_total = ""

  with pdfplumber.open(pdf_file) as pdf:
    for i, page in enumerate(pdf.pages):
      texto_pagina = page.extract_text()
      if not texto_pagina:
        continue

      if debug:
        texto_total += (
            f"\n--- PÁGINA {i+1} ---\n" + texto_pagina
        )  # Acumula para exibir se debug ativado

      linhas = texto_pagina.split("\n")
      codigo_empregado = None
      base_irrf = None

      for linha in linhas:
        # 1. Busca flexível para Código do Empregado
        match_emp = re.search(
            r"(?:C[oó]d\.?|Matr[ií]c\.?|Empreg\.?|Funcion[aá]rio)[:\s]*(\d+)",
            linha,
            re.IGNORECASE,
        )
        if match_emp:
          codigo_empregado = match_emp.group(1)

        # 2. Busca flexível para Base de IRRF (cobre diferentes nomenclaturas de sistemas de folha)
        match_irrf = re.search(
            r"(?:Base\s*(?:de\s*)?IRRF|BC\s*IRRF|IRRF\s*Base|Base\s*Calc\.?\s*IRRF)[:\s]*([\d\.,]+)",
            linha,
            re.IGNORECASE,
        )
        if match_irrf:
          base_irrf_str = match_irrf.group(1)
          try:
            # Limpa formato monetário (remove pontos de milhar e troca vírgula por ponto)
            base_irrf_limpo = (
                base_irrf_str.replace(".", "").replace(",", ".").strip()
            )
            # Evita capturar valores vazios ou pontuações isoladas
            if base_irrf_limpo and base_irrf_limpo != ".":
              base_irrf = float(base_irrf_limpo)
          except ValueError:
            pass

      # Se encontrou ambos os campos na página ou acumulados
      if codigo_empregado and base_irrf is not None:
        dados_extraidos.append(
            {
                "Arquivo": pdf_file.name,
                "codigo_empregado": codigo_empregado,
                "base_irrf": base_irrf,
            }
        )

  if debug and texto_total:
    st.text_area(
        f"Texto Extraído do Arquivo: {pdf_file.name}",
        texto_total,
        height=200,
    )

  return dados_extraidos


if uploaded_files:
  st.subheader("📁 Resumo dos Dados Extraídos")

  todos_dados = []

  for arquivo in uploaded_files:
    resultados = extrair_dados_pdf(arquivo, debug=modo_debug)
    if resultados:
      todos_dados.extend(resultados)
    else:
      st.warning(
          f"⚠️ Não foi possível extrair dados automaticamente do arquivo"
          f" **{arquivo.name}**. Verifique se o PDF contém texto selecionável"
          f" ou ative o 'Modo Debug' na barra lateral para inspecionar o"
          f" conteúdo lido."
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
