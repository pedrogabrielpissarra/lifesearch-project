# LifeSearch Web Application

Esta é uma aplicação web Flask que permite aos usuários buscar informações sobre exoplanetas, configurar pesos de habitabilidade e gerar relatórios detalhados com visualizações gráficas.

## Estrutura do Projeto

```
/lifesearch/
├── app/                           # Contém o código da aplicação Flask
│   ├── __init__.py              # Inicializa a aplicação Flask, configura e registra rotas
│   ├── forms.py                 # Define os formulários WTForms (PlanetSearchForm, HabitabilityWeightsForm, PHIWeightsForm)
│   ├── routes.py                # Define as rotas da aplicação (index, configure, results, etc.)
│   ├── static/                  # Arquivos estáticos (CSS, JS, imagens de gráficos gerados)
│   │   └── charts/              # Diretório para gráficos gerados (dentro de cada pasta de resultado)
│   └── templates/               # Templates HTML Jinja2
│       ├── index.html           # Página inicial com formulário de busca
│       ├── configure.html       # Página para configurar pesos de habitabilidade
│       ├── results.html         # Página para exibir links para os relatórios gerados
│       ├── report_template.html   # Template para relatórios individuais de planetas
│       ├── summary_template.html  # Template para o relatório resumido
│       ├── combined_template.html # Template para o relatório combinado
│       └── error.html           # Template para páginas de erro (404, 500)
├── lifesearch/                    # Contém a lógica principal do programa LifeSearch
│   ├── __init__.py              # Arquivo de inicialização do módulo lifesearch
│   ├── data.py                  # Funções para buscar dados da API, carregar CSVs locais e mesclar fontes de dados
│   ├── reports.py               # Funções para gerar relatórios HTML e gráficos (plots)
│   ├── lifesearch_main.py       # Lógica principal para processar dados de planetas e calcular scores
│   ├── cache/                   # Diretório para armazenar dados da API em cache (arquivos JSON)
│   └── data/                    # Arquivos de dados CSV locais
│       ├── hwc.csv              # Catálogo HWC
│       └── table-hzgallery.csv  # Catálogo HZGallery
├── lifesearch_results/            # Diretório onde os resultados (relatórios e gráficos) são salvos
│   └── lifesearch_results_YYYYMMDD_HHMMSS/ # Subdiretório específico da sessão com relatórios
│       ├── charts/              # Gráficos para esta sessão
│       └── *.html               # Relatórios HTML
├── run.py                       # Script para iniciar o servidor de desenvolvimento Flask
├── requirements.txt             # Lista de dependências Python do projeto
├── todo.md                      # Lista de tarefas do desenvolvimento
└── README.md                    # Este arquivo
```

## Configuração e Execução

1.  **Pré-requisitos**:
    *   Python 3.8 ou superior
    *   `pip` para instalar dependências

2.  **Clonar o repositório (ou extrair os arquivos do ZIP)**:
    Navegue até o diretório onde deseja salvar o projeto.

3.  **Criar e Ativar um Ambiente Virtual (Recomendado)**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # No Linux/macOS
    # venv\Scripts\activate    # No Windows
    ```

4.  **Instalar Dependências**:
    No diretório raiz do projeto (onde `requirements.txt` está localizado), execute:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configurar a Chave Secreta do Flask (Opcional para Desenvolvimento)**:
    A aplicação usa uma chave secreta padrão para desenvolvimento. Para produção, é altamente recomendável definir uma variável de ambiente `FLASK_SECRET_KEY` com um valor seguro.

6.  **Executar a Aplicação**:
    No diretório raiz do projeto, execute:
    ```bash
    python run.py
    ```
    A aplicação estará acessível em `http://0.0.0.0:5000/` ou `http://127.0.0.1:5000/` no seu navegador.

## Funcionalidades

*   **Página Inicial (`/`)**: Permite ao usuário inserir nomes de exoplanetas (separados por vírgula ou nova linha) e, opcionalmente, sobrescrever parâmetros específicos para cada planeta.
*   **Página de Configuração (`/configure`)**: Permite ao usuário ajustar os pesos para diferentes fatores de habitabilidade (ESI, SPH) e para os componentes do PHI. Esses pesos são salvos na sessão do usuário.
*   **Página de Resultados (`/results`)**: Após a busca, esta página exibe links para os relatórios gerados:
    *   Relatórios individuais para cada planeta processado.
    *   Relatório resumido (se múltiplos planetas forem processados).
    *   Relatório combinado (se múltiplos planetas forem processados).
*   **Relatórios**: Os relatórios HTML incluem informações detalhadas sobre o planeta, estrela, órbita, scores de habitabilidade (ESI, SPH, PHI) e gráficos (Zona Habitável, Comparação de Scores).
*   **Cache**: Os dados da API do NASA Exoplanet Archive são cacheados para melhorar o desempenho e reduzir o número de chamadas à API. O cache expira após 24 horas.
*   **Logging**: A aplicação registra informações sobre seu funcionamento, incluindo chamadas à API, processamento de dados e erros.

## Como Usar

1.  Acesse a página inicial.
2.  (Opcional) Vá para a página "Configurar Pesos" para ajustar os pesos dos fatores de habitabilidade. As configurações padrão serão usadas caso contrário.
3.  Na página inicial, insira os nomes dos planetas que deseja analisar.
    *   Exemplo: `Kepler-452 b, TRAPPIST-1 e`
4.  (Opcional) Use o campo "Sobrescrever Parâmetros" para fornecer valores customizados.
    *   Formato: `NomeDoPlaneta: param1=valor1; param2=valor2` (uma linha por planeta)
    *   Exemplo: `Kepler-452 b: pl_rade=2.4; st_age=6.0`
5.  Clique em "Buscar Planetas".
6.  A página de resultados mostrará links para os relatórios gerados. Clique nos links para visualizar os relatórios.

## Observações

*   A precisão dos cálculos de habitabilidade (ESI, SPH, PHI) depende da completude e correção das fórmulas adaptadas do script original `lifesearch11.py`. As implementações atuais em `lifesearch/lifesearch_main.py` são placeholders e precisam ser revisadas e completadas com a lógica científica exata do seu script original para garantir resultados corretos.
*   Os gráficos são salvos como imagens PNG no diretório `lifesearch_results/nome_da_sessao_YYYYMMDD_HHMMSS/charts/` e são referenciados nos relatórios HTML.
*   Para implantação em produção, use um servidor WSGI como Gunicorn ou Waitress em vez do servidor de desenvolvimento do Flask.

