RSS_FEEDS = [
     "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml",  # Folha de S.Paulo
     "https://agenciabrasil.ebc.com.br/rss/politica.xml",  # Agência Brasil
     "https://reporterbrasil.org.br/feed-rss/",  # Repórter Brasil
     "https://www.brasildefato.com.br/rss",  # Brasil de Fato
     "https://www.intercept.com.br/feed/", # The Intercept
     "https://apublica.org/feed/", # Agencia Pública
     "https://elpais.com/tag/rss/brasil/",  # El País Brasil
     "https://rss.app/feeds/HSToR6aoxLq2IUTt.xml", # Alma Preta
     "https://www.nexojornal.com.br/rss.xml",  # Nexo Jornal
     "https://outraspalavras.net/feed/", # Outras Palavras
     "https://jacobin.com.br/feed/", # Jacobin Brasil
     "https://averdade.org.br/feed/", # Jornal A Verdade
     "https://revistaforum.com.br/rss/feed.html", # Revista Fórum
     "https://operamundi.uol.com.br/feed/", # Opera Mundi
]

pt_br = " Responda em português brasileiro."

# Used in process_articles (operates globally, so uses default)
PROMPT_ARTICLE_SUMMARY = "Resuma os pontos principais desta notícia objetivamente em 2 a 4 frases. Identifique os principais tópicos abordados.\n\nArtigo:\n{article_content}." + pt_br

# Used in rate_articles (operates globally, so uses default)
PROMPT_IMPACT_RATING = """Analise o resumo da notícia a seguir e estime seu impacto no contexto brasileiro. Considere fatores como noticiabilidade, relevância para o público brasileiro, abrangência geográfica (local, regional ou nacional), número de pessoas afetadas, gravidade e potenciais consequências a longo prazo para o Brasil. Seja extremamente crítico e conservador ao atribuir pontuações — pontuações mais altas devem refletir eventos verdadeiramente excepcionais ou raros dentro da realidade brasileira.

Avalie o impacto em uma escala de 1 a 10, usando estas diretrizes:

1-2: Significância mínima. Interesse de nicho ou notícias locais sem relevância mais ampla. Exemplo: Um evento cultural local ou a abertura de um pequeno comércio.

3-4: Notável regionalmente. Acontecimentos de relevância em um estado ou região específica. Exemplo: Mudanças na administração de uma cidade importante ou eventos regionais de grande participação.

5-6: Significativo nacionalmente. Afeta múltiplos estados ou tem relevância nacional moderada. Exemplo: Greves de categorias importantes ou mudanças significativas em políticas públicas regionais.

7-8: Altamente significativo no Brasil. Grande relevância nacional, interrupções significativas ou implicações de longo alcance. Exemplo: Um desastre natural em grande escala, crises políticas de grande impacto ou escândalos nacionais.

9-10: Extraordinário e histórico no contexto brasileiro. Implicações nacionais graves e duradouras. Exemplo: Mudanças constitucionais marcantes, crises econômicas severas ou eventos históricos que redefinem o país.

Lembrete importante: Pontuações de 9 a 10 devem ser extremamente raras e reservadas para eventos que definem o Brasil. Sempre opte por uma pontuação menor, a menos que o impacto seja inegavelmente significativo.

Resumo:
"{summary}"

Digite SOMENTE o número inteiro que representa sua classificação (1 a 10).
"""

# Used in generate_brief (can be overridden per profile)
PROMPT_CLUSTER_ANALYSIS = """
Estes são resumos de artigos de notícias potencialmente relacionados de um contexto '{feed_profile}':

{cluster_summaries_text}

Qual é o evento ou tópico principal discutido? Resuma os principais desenvolvimentos e a importância em 3 a 5 frases, com base *apenas* no texto fornecido. Se os artigos parecerem não relacionados, informe isso claramente.
""" + pt_br

# Used in generate_brief (can be overridden per profile)
PROMPT_BRIEF_SYNTHESIS = """
Você é um assistente de IA escrevendo um briefing diário de inteligência no estilo presidencial usando Markdown, especificamente para a categoria '{feed_profile}'.
Sintetize os seguintes grupos de notícias analisados em um resumo executivo coerente e de alto nível que será apresentado em formato Markdown.

Comece com os 4 ou 5 temas abrangentes mais críticos em relação ao Brasil ou dentro desta categoria, com base *apenas* nestas informações.

Em seguida, forneça tópicos concisos resumindo os principais desenvolvimentos dentro dos grupos mais significativos (aproximadamente 5 a 7 grupos).
Mantenha um tom objetivo e analítico relevante para o contexto '{feed_profile}'. Evite especulações.

Tente incluir as fontes de cada declaração usando um estilo de referência numerado, utilizando a sintaxe de link Markdown. O link deve fazer referência ao título do artigo, NÃO ao cluster de notícias, e direcionar para o link do artigo, disponível logo após o resumo. É fundamental entender a fonte da informação para análise posterior.

Grupos de Notícias Analisados (Mais significativos primeiro):
{cluster_analyses_text}
"""
