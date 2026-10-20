# MotoX — Conferência Inteligente de Planilhas (versão online)

Aplicativo web com dashboard para comparar a planilha dos motoristas auxiliares com a planilha principal da MotoX.

## O que faz
- Upload de duas planilhas Excel pelo navegador.
- Seleção de abas e colunas com sugestões automáticas.
- Comparação por nome normalizado.
- Sinalização de divergências de valor, nomes ausentes e nomes duplicados.
- Dashboard com indicadores e totais.
- Exportação de relatório Excel com abas Comparacao, Nomes_Duplicados, Pendencias e Resumo.

## Como publicar online gratuitamente (Streamlit Community Cloud)
Este pacote está pronto para publicação, mas ainda não está hospedado/publicado. Para obter um link público, é necessário usar uma conta de hospedagem:

1. Entre em https://github.com e crie um repositório novo, por exemplo `motox-conferencia-planilhas`.
2. Envie para esse repositório os arquivos `app.py` e `requirements.txt` desta pasta.
3. Entre em https://share.streamlit.io/ e conecte sua conta GitHub.
4. Escolha o repositório, selecione `app.py` como arquivo principal e clique em Deploy.
5. A plataforma fornecerá um endereço web para abrir o dashboard.

## Teste local opcional
No Terminal, dentro desta pasta:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Acesse http://localhost:8501.

## Segurança e limitações
- O aplicativo não faz pagamentos nem altera os arquivos originais.
- Confira as colunas selecionadas antes de confiar no resultado.
- Para uso online, não envie dados pessoais/financeiros confidenciais a uma hospedagem pública sem aprovação da empresa e avaliação das configurações de acesso e retenção.
- A comparação usa nome normalizado; nomes iguais são agregados por pessoa, e duplicidades são mostradas separadamente.
