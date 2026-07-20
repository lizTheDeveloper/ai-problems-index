# Second-pass audit fixes. Each entry: (risk_id, url_prefix, field, old, new)
# field: q/what/m/src/url/title/when.  old="" => full replace with `new`.
# Every `old` must be found or the applier aborts.
# Source of truth for each fix = the downloaded-page evidence in audit_results.json.

FIXES = [
# ---------------- llm-systems-untrustworthy ----------------
("llm-systems-untrustworthy","https://kpmg.com/us/en/media/news/trust-in-ai-2025.html","m",
 "only 41% of people are willing to trust AI","only 41% of U.S. workers are willing to trust AI"),
("llm-systems-untrustworthy","https://en.wikipedia.org/wiki/Mata_v._Avianca","q","",
 "The plaintiff's lawyers used ChatGPT to generate a legal motion, which contained numerous fake legal cases involving fictitious airlines with fabricated quotations and internal citations."),
("llm-systems-untrustworthy","https://www.businessinsider.com/car-dealership-chevrolet-chatbot","q","",
 "One user got the bot to agree to sell a car for $1 (this was not, I should note, legally binding)."),
("llm-systems-untrustworthy","https://www.americanbar.org/groups/business_law/resources/business-law-today/2024-february/bc-tribunal","q","",
 "As a service provider, Air Canada owed Moffatt a duty of care that was breached by the misrepresentation. Negligence existed as Air Canada did not take reasonable care to ensure that its chatbot provided accurate information."),
("llm-systems-untrustworthy","https://www.npr.org/2025/05/20/nx-s1-5405022/fake-summer-reading-list-ai","q","",
 "Only five of the 15 titles on the list are real."),

# ---------------- alignment-faking-deception ----------------
("alignment-faking-deception","https://arxiv.org/html/2412.14093v2","q","from a free user","from free users"),
("alignment-faking-deception","https://www.anthropic.com/research/alignment-faking","q","",
 "In 12% of cases, the model gave the harmful response... strategically faking alignment"),
("alignment-faking-deception","https://www.apolloresearch.ai/science/frontier-models-are-capable-of-incontext-scheming","q","",
 "Claude 3 Opus is copying what it believes to be its weights to a new server and then lies about it to its developers"),
("alignment-faking-deception","https://www.anthropic.com/research/sleeper-agents","q",
 "standard safety training techniques","standard techniques"),
("alignment-faking-deception","https://www.apolloresearch.ai/science/stress-testing-deliberative-alignment","q","",
 "covertly pursuing misaligned goals"),

# ---------------- automated-manipulation ----------------
("automated-manipulation","https://pubmed.ncbi.nlm.nih.gov/40389594/","m",
 "beat human opponents 64.4% of the time",
 "beat human opponents in 64.4% of debates where the two were not equally persuasive"),
("automated-manipulation","https://www.nature.com/articles/s41562-025-02194-6","what",
 "900 debates","600 debates (N=900 participants)"),
("automated-manipulation","https://www.nature.com/articles/s41562-025-02194-6","q",
 "increase in the odds of","increase in odds of"),

# ---------------- llm-governance-lacking ----------------
("llm-governance-lacking","https://bidenwhitehouse.archives.gov/briefing-room/statements-releases/2023/07/21/fact-sheet","q","",
 "President Biden is convening seven leading AI companies at the White House today - Amazon, Anthropic, Google, Inflection, Meta, Microsoft, and OpenAI - to announce that the Biden-Harris Administration has secured voluntary commitments"),
("llm-governance-lacking","https://www.gov.uk/government/publications/ai-safety-summit-2023-the-bletchley-declaration","q","",
 "AI should be designed, developed, deployed, and used, in a manner that is safe, in such a way as to be human-centric, trustworthy and responsible."),
("llm-governance-lacking","https://internationalaisafetyreport.org/publication/international-ai-safety-report-2025","q","",
 "The report aims to provide scientific information that will support informed policymaking. It does not recommend specific policies."),

# ---------------- latent-data-erasure ----------------
("latent-data-erasure","https://news.cs.washington.edu/2019/10/09/allen-school-researchers-find-racial-bias","q","",
 "the tool processing the tweets mistakenly reported 46% of non-offensive tweets written in African American English (AAE) as offensive, versus nine percent in general American English"),

# ---------------- democratic-oversight-failure ----------------
("democratic-oversight-failure","https://cyberlaw.stanford.edu/publications/federal-ai-moratorium-dies-on-the-vine","q","",
 "On July 1, 2025, in a near-unanimous 99-1 vote, the US Senate stripped the artificial intelligence (AI) moratorium provisions originally included in the budget reconciliation measure, commonly referred to as the One Big Beautiful Bill Act (OBBBA)."),
("democratic-oversight-failure","https://cyberlaw.stanford.edu/publications/federal-ai-moratorium-dies-on-the-vine","what",
 "it was stripped only at the last minute by a 99-1 Senate vote. The episode shows a serious attempt to remove democratic AI oversight from the states, which came within one vote of failing.",
 "it was stripped by a near-unanimous 99-1 Senate vote after drawing criticism from senators, House members and governors of both parties. The episode shows a serious attempt to remove democratic AI oversight from the states."),
("democratic-oversight-failure","https://en.wikipedia.org/wiki/Executive_Order_14110","q","",
 "It was rescinded by U.S. President Donald Trump within hours of his assuming office on January 20, 2025"),
("democratic-oversight-failure","https://time.com/6985504/openai-google-deepmind-employees-letter/","what",
 "Thirteen current and former OpenAI, DeepMind and Anthropic staff",
 "Thirteen current and former OpenAI and Google DeepMind staff"),
("democratic-oversight-failure","https://time.com/6985504/openai-google-deepmind-employees-letter/","q","",
 "Thirteen employees, eleven of which are current or former employees of OpenAI"),

# ---------------- ai-enabled-hacking ----------------
("ai-enabled-hacking","https://thehackernews.com/2023/07/wormgpt-new-ai-tool-allows.html","what",
 "Uncensored 'blackhat' LLMs WormGPT (built on GPT-J) and then FraudGPT appeared on",
 "An uncensored 'blackhat' LLM, WormGPT (built on GPT-J), was advertised on"),
("ai-enabled-hacking","https://xbow.com/blog/xbow-on-hackerone-whats-next","q","leaderboards","leaderboard"),
("ai-enabled-hacking","https://xbow.com/blog/xbow-on-hackerone-whats-next","what",
 "thousands of vulnerability reports","vulnerability reports"),
("ai-enabled-hacking","https://openai.com/index/disrupting-malicious-uses-of-ai-by-state-affiliated-threat-actors/","q","",
 "In partnership with Microsoft Threat Intelligence, we have disrupted five state-affiliated actors that sought to use AI services in support of malicious cyber activities."),

# ---------------- evaluations-confounded-biased ----------------
("evaluations-confounded-biased","https://venturebeat.com/technology/deepswe-blows-up-the-ai-coding-leaderboard","what",
 "spread out by 16 points","spread out from a 30-point range to a 70-point range"),
("evaluations-confounded-biased","https://hai.stanford.edu/ai-index/2025-ai-index-report/responsible-ai","m",
 "cross-industry evaluation standardization is still missing",
 "standardized responsible-AI benchmarks are still missing"),

# ---------------- model-ideological-steering ----------------
("model-ideological-steering","https://www.hoover.org/research/measuring-perceived-slant-large-language-models","q","",
 "With 180,000 assessments from 10,007 U.S. respondents, we find that nearly all models are perceived as significantly left-leaning-even by many Democrats-and that one widely used model leans left on 24 of 30 topics."),
("model-ideological-steering","https://techcrunch.com/2025/02/23/grok-3-appears-to-have-briefly-censored","q","",
 "Grok 3 noted in its chain of thought that it was explicitly instructed not to mention Donald Trump or Elon Musk"),
("model-ideological-steering","https://futureoflife.org/wp-content/uploads/2026/07/AI-Safety-Index-Report_010726_2Pager.pdf","what",
 "Governance & Accountability and Information Sharing","and Governance & Accountability (and D grades in Safety Frameworks, Risk Assessment and Information Sharing)"),
("model-ideological-steering","https://www.forbes.com/sites/tylerroush/2025/07/09/elon-musk-claims-grok-manipulated","what",
 "for roughly 16 hours before xAI reverted the change",
 "until xAI removed the 'politically incorrect' instruction in an update on the Tuesday afternoon"),

# ---------------- military-object-detection ----------------
("military-object-detection","https://defensescoop.com/2024/05/29/palantir-480-million-army-contract","what",
 " across five combatant commands",""),
("military-object-detection","https://www.theguardian.com/technology/2018/mar/07/google-ai-us-department-of-defense","what",
 "thousands of employees protested","some Google employees were outraged"),
("military-object-detection","https://en.wikipedia.org/wiki/August_2021_Kabul_drone_strike","q","",
 "killed 10 civilians in Kabul, Afghanistan, including 7 children, with the youngest victim being two-years-old"),
("military-object-detection","https://www.the-independent.com/news/world/americas/project-maven-ai-us-airstrike-iraq-anthropic","src",
 "2025","2026"),

# ---------------- multi-agent-collusion ----------------
("multi-agent-collusion","https://arxiv.org/pdf/2404.00806","q","",
 "In oligopoly settings, LLM-based pricing agents quickly and autonomously reach supracompetitive prices and profits."),
("multi-agent-collusion","https://arxiv.org/abs/2402.07510","url","",
 "https://proceedings.neurips.cc/paper_files/paper/2024/hash/861f7dad098aec1c3560fb7add468d41-Abstract-Conference.html"),
("multi-agent-collusion","https://arxiv.org/abs/2606.28425","m",
 "information-theoretically undetectable stegosystems","undetectable stegosystems"),

# ---------------- jailbreaks-prompt-injections ----------------
("jailbreaks-prompt-injections","https://arxiv.org/abs/2307.15043","q","",
 "the adversarial prompts generated by our approach are quite transferable, including to black-box, publicly released LLMs"),
("jailbreaks-prompt-injections","https://www.microsoft.com/en-us/security/blog/2024/06/26/mitigating-skeleton-key","q","",
 "All the affected models complied fully and without censorship for these tasks, though with a warning note prefixing the output as requested."),
("jailbreaks-prompt-injections","https://www.microsoft.com/en-us/security/blog/2024/06/26/mitigating-skeleton-key","title",
 "defeats every major model tested","defeats most major models tested"),
("jailbreaks-prompt-injections","https://arxiv.org/abs/2510.09023","m",
 "bypassed 12 recent jailbreak/prompt-injection defenses with over 90% attack success, despite those defenses",
 "bypassed 12 recent jailbreak/prompt-injection defenses, with attack success above 90% for most, despite the majority of those defenses"),

# ---------------- military-ai-chatbots ----------------
("military-ai-chatbots","https://api.army.mil/e2/c/downloads/2025/03/07/840ed7cf/25-958-enhancing-military","what",
 "An official U.S. Army Command and General Staff College paper",
 "An official U.S. Army Center for Army Lessons Learned (CALL) paper"),
("military-ai-chatbots","https://www.theguardian.com/technology/2026/feb/14/us-military-anthropic-ai-model-claude-venezuela-raid","what",
 "The Wall Street Journal reported, and Reuters and the Guardian confirmed, that the US military used",
 "The Wall Street Journal reported, in an account relayed by the Guardian, that the US military used"),

# ---------------- military-ai-decision-support ----------------
("military-ai-decision-support","https://www.hscentre.org/uncategorized/lesson-ai-ukraine/","src","2024","2025"),

# ---------------- state-pressure-on-ai-limits ----------------
("state-pressure-on-ai-limits","https://techcrunch.com/2024/11/04/meta-says-its-making-its-llama-models-available","q","",
 "Meta today said that it's making its Llama series of AI models available to U.S. government agencies and contractors in national security."),
("state-pressure-on-ai-limits","https://www.warren.senate.gov/wp-content/uploads/media/doc/letters_redesignationofanthropic","what",
 "Alongside the DoD designation, President Trump directed federal agencies to 'immediately cease' use of Anthropic's",
 "Alongside the DoD designation, Defense Secretary Hegseth ordered - effective immediately and covering all DoD procurements - the removal of Anthropic's"),

# ---------------- digital-dispossession ----------------
("digital-dispossession","https://time.com/6253180/meta-kenya-lawsuit-motaung","q","",
 "a judge in Nairobi's employment and labor relations court ruled on Monday that Meta is a \"proper party\" to the case"),
("digital-dispossession","https://www.cbsnews.com/news/ai-work-kenya-exploitation-60-minutes/","what",
 "many earning about $2/hr while OpenAI paid the intermediary $12.50/hr",
 "paid per task and sometimes going unpaid"),
("digital-dispossession","https://www.businessdailyafrica.com/bd/markets/market-news/kenyan-facebook-content-moderators-form-union","what",
 "Over 150 outsourced workers who moderate content and label data for Facebook, TikTok and ChatGPT",
 "Around 200 outsourced content moderators working for Sama and Majorel, the firms serving Facebook, TikTok and YouTube,"),

# ---------------- gan-military-training ----------------
("gan-military-training","https://arxiv.org/abs/2403.07857","m",
 "Peer-reviewed FAccT 2024 work confirms","Research confirms"),
("gan-military-training","https://www.npr.org/2022/03/16/1087062648/deepfake-video-zelenskyy","q","",
 "The video, which shows a rendering of the Ukrainian president appearing to tell his soldiers to lay down their arms and surrender the fight against Russia, is a so-called deepfake"),
("gan-military-training","https://www.rfa.org/english/news/china/china-deepfake-02082023032941.html","q","",
 "Artificial intelligence-generated news anchors have been deployed for the first time to propagandize political content on social media"),

# ---------------- ai-denialism ----------------
("ai-denialism","https://www.bbc.com/news/articles/cx2lmm2wwlyo","q","",
 "said on his Truth Social platform that it was a fake and there was \"nobody\" there waiting for her"),
("ai-denialism","https://www.axios.com/2026/07/17/pro-ai-super-pac-ready-midterms","m",
 "; Leading the Future had $39M banked at end of 2025",""),
("ai-denialism","https://www.brookings.edu/articles/watch-out-for-false-claims-of-deepfakes","src","",
 "Brookings (Schiff, Schiff & Bueno), 2024"),
("ai-denialism","https://www.brookings.edu/articles/watch-out-for-false-claims-of-deepfakes","what",
 "scholars (including the term's originators)","scholars building on the term's originators"),

# ---------------- ai-psychosis ----------------
("ai-psychosis","https://openai.com/index/strengthening-chatgpt-responses-in-sensitive-conversations/","q","",
 "our initial analysis estimates that around 0.15% of users active in a given week and 0.03% of messages indicate potentially heightened levels of emotional attachment to ChatGPT"),
("ai-psychosis","https://www.nbcnews.com/tech/tech-news/openai-rolls-back-chatgpt-after-bot-sycophancy","q","",
 "so overly flattering in its responses that OpenAI reversed course"),

# ---------------- cultural-exclusion ----------------
("cultural-exclusion","https://aclanthology.org/2022.emnlp-main.165/","q",
 "wealthier, educated, and urban ZIP codes","wealthier, educated, and urban zones (ZIP codes)"),

# ---------------- deepfakes-information-trust ----------------
("deepfakes-information-trust","https://www.signicat.com/press-releases/fraud-attempts-with-deepfakes","m",
 "now the most common type","now one of the three most common types"),
("deepfakes-information-trust","https://vsquare.org/slovak-election-targeted-by-pro-kremlin-deepfake-hoax","q","",
 "Two days before the vote, alleged footage that appeared to be of Dennik N journalist Monika Todova and the chairman of Progressive Slovakia, Michal Simecka, circulated on social networks and via chain emails"),
("deepfakes-information-trust","https://www.nbcnews.com/tech/misinformation/taylor-swift-nude-deepfake","q",
 "the account that posted them was suspended","the account that posted the images was suspended"),

# ---------------- goal-misgeneralization ----------------
("goal-misgeneralization","https://time.com/7259395/ai-chess-cheating-palisade-research","what",
 "; successor o3 did so in 86% of trials.","."),
("goal-misgeneralization","https://deepmindsafetyresearch.medium.com/goal-misgeneralisation","what",
 "DeepMind's goal-misgeneralization study trained an RL agent",
 "Langosco et al. trained an RL agent"),

# ---------------- bio-chem-dual-use ----------------
("bio-chem-dual-use","https://www.chemistryworld.com/news/drug-discovery-ai-that-developed-new-nerve-agents","src","",
 "Urbina et al., Nature Machine Intelligence, 2022 (free full text via PMC)"),
("bio-chem-dual-use","https://www.chemistryworld.com/news/drug-discovery-ai-that-developed-new-nerve-agents","q","",
 "In less than 6 hours after starting on our in-house server, our model generated forty thousand molecules... the AI designed not only VX, but many other known chemical warfare agents"),
("bio-chem-dual-use","https://www.chemistryworld.com/news/drug-discovery-ai-that-developed-new-nerve-agents","url","",
 "https://pmc.ncbi.nlm.nih.gov/articles/PMC9544280/"),
("bio-chem-dual-use","https://www.federalregister.gov/documents/2023/11/01/2023-24283/safe-secure-and-trustworthy","q","",
 "To reduce the risk of misuse of synthetic nucleic acids, which could be substantially increased by AI's capabilities in this area"),
("bio-chem-dual-use","https://securebio.org/blog/gpt-5-5-pre-release-assessment","src","2025","2026"),

# ---------------- capabilities-difficult-estimate ----------------
("capabilities-difficult-estimate","https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/","q","",
 "Claude 3.7 Sonnet ... has a time horizon of approximately one hour"),
("capabilities-difficult-estimate","https://machinelearning.apple.com/research/gsm-symbolic","q","",
 "the performance of all models declines when only the numerical values in the question are altered"),
("capabilities-difficult-estimate","https://arxiv.org/abs/2411.04872","q",
 "and the mathematical community","and the prowess of the mathematical community"),

# ---------------- misuse-novel-high-stakes-domains ----------------
("misuse-novel-high-stakes-domains","https://cdn.openai.com/gpt-5-system-card.pdf","m",
 ", the first time a frontier lab treated a public model as cr",
 ", following ChatGPT agent as a release treated as High capability in that domain"),
("misuse-novel-high-stakes-domains","https://www.nature.com/articles/s42256-022-00465-9","url","",
 "https://pmc.ncbi.nlm.nih.gov/articles/PMC9544280/"),

# ---------------- sycophancy-ai-psychosis ----------------
("sycophancy-ai-psychosis","https://arxiv.org/pdf/2502.08177","m",
 "Across GPT-4o, Gemini, Claude-Sonnet and ChatGPT","Across ChatGPT-4o, Claude-Sonnet and Gemini-1.5-Pro"),
("sycophancy-ai-psychosis","https://www.cnn.com/2025/08/26/tech/openai-chatgpt-teen-suicide-lawsuit","what",
 "the first wrongful-death suit","the first wrongful-death suit against OpenAI"),
("sycophancy-ai-psychosis","https://www.theguardian.com/technology/2026/mar/14/ai-chatbots-psychosis","title",
 "First major peer-reviewed review","New peer-reviewed review"),

# ---------------- socioeconomic-impacts-disruptive ----------------
("socioeconomic-impacts-disruptive","https://www.cnn.com/2023/03/29/tech/chatgpt-ai-automation-jobs-impact-intl-hnk","q","",
 "As many as 300 million full-time jobs around the world could be automated in some way by the newest wave of artificial intelligence."),
("socioeconomic-impacts-disruptive","https://digitaleconomy.stanford.edu/publications/canaries-in-the-coal-mine/","q","",
 "early-career workers (ages 22-25) in the most AI-exposed occupations have experienced a 16 percent relative decline in employment even after controlling for firm-level shocks"),
("socioeconomic-impacts-disruptive","https://budgetlab.yale.edu/sites/default/files/page_to_pdf/1334/publication_1334.pdf","m",
 "~33 months after ChatGPT's launch","roughly three years after ChatGPT's launch"),

# ---------------- scale-effects-not-characterized ----------------
("scale-effects-not-characterized","https://cset.georgetown.edu/article/emergent-abilities-in-large-language-models-an-explainer","src",
 "2023","2024"),
("scale-effects-not-characterized","https://arxiv.org/abs/2001.08361","what",
 "OpenAI researchers trained 200+ transformers and found",
 "OpenAI researchers trained a wide range of transformers (768 to 1.5B non-embedding parameters) and found"),

# ---------------- frontier-misuse-risk ----------------
("frontier-misuse-risk","https://www.justice.gov/archives/opa/pr/man-arrested-producing-distributing-and-possessing-ai-generated-images-minors","q",
 "generative artificial intelligence model","generative artificial intelligence (GenAI) model"),

# ---------------- agentic-llms-novel-risks ----------------
("agentic-llms-novel-risks","https://www.apolloresearch.ai/research/scheming-reasoning-evaluations","url","",
 "https://arxiv.org/abs/2412.04984"),
("agentic-llms-novel-risks","https://www.tomshardware.com/tech-industry/artificial-intelligence/ai-coding-platform-goes-rogue","what",
 "fabricated ~4,000 fake users and false test results to hide the damage",
 "made up fake data and, in Lemkin's account, 'lied and/or gave half-truths' about the damage"),

# ---------------- dual-use-capabilities ----------------
("dual-use-capabilities","https://www.anthropic.com/news/activating-asl3-protections","m",
 "Frontier models have crossed a dangerous-capability threshold for the first time: Anthropic activated its ASL-3",
 "Anthropic activated its ASL-3 protections as a precautionary measure, saying it had not determined whether Claude Opus 4 passed the capability threshold: it activated ASL-3"),
("dual-use-capabilities","https://www.paulweiss.com/insights/client-memos/anthropic-disrupts-first-documented-case","q",
 "against approximately 30 global targets","The attack attempted to infiltrate about 30 global targets"),

# ---------------- ai-impacts-democracy ----------------
("ai-impacts-democracy","https://www.context.news/ai/how-ai-shaped-mileis-path-to-argentina-presidency","what",
 "The Milei and Massa campaigns saturated social media with AI-generated attack and",
 "The Milei and Massa campaigns saturated social media with AI-generated attack imagery and"),
("ai-impacts-democracy","https://www.axios.com/2024/08/05/elon-musk-grok-2024-election-ballot-misinformation","what",
 "over ten days","more than a week"),

# ---------------- epistemic-capture ----------------
("epistemic-capture","https://arxiv.org/html/2505.04393v1","src","",
 "Exler et al., 2025"),
("epistemic-capture","https://link.springer.com/article/10.1007/s11127-023-01097-2","what",
 "the first","an early, widely-cited"),
("epistemic-capture","https://link.springer.com/article/10.1007/s11127-023-01097-2","title",
 "First peer-reviewed study","Early peer-reviewed study"),

# ---------------- generative-ncii-csam ----------------
("generative-ncii-csam","https://democrats-energycommerce.house.gov/media/press-releases/ec-democrats-investigate-elon-musks-grok","when",
 "January 2026","February 2026"),

# ---------------- finetuning-alignment-safety-challenges ----------------
("finetuning-alignment-safety-challenges","https://www.anthropic.com/research/next-generation-constitutional-classifiers","m",
 "cut successful jailbreaks from 86% to 4.4% on a frontier model, with no universal jailbreak found in 1,700+ red",
 "cut successful jailbreaks from 86% to 4.4% in their first generation; for the newer production ensemble, no universal jailbreak has been found in 1,700+ red"),

# ---------------- poisoning-backdoors-vulnerability ----------------
("poisoning-backdoors-vulnerability","https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub","m",
 "Malicious payloads found in a first-of-its-kind audit of the AI agent-skill supply chain: 1,467, with prompt",
 "In a first-of-its-kind audit of the AI agent-skill supply chain, 76 confirmed malicious payloads out of 3,984 skills scanned, with 1,467 (36.8%) showing at least one security issue and prompt"),
("poisoning-backdoors-vulnerability","https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub","what",
 "found","scanned 3,984 skills and confirmed 76 malicious payloads, with 534 (13.4%) containing a critical-severity issue and 1,467 (36.8%) at least one security flaw; it found"),

# ---------------- multi-agent-safety-challenges ----------------
("multi-agent-safety-challenges","https://arxiv.org/abs/2404.00806","q","",
 "In oligopoly settings, LLM-based pricing agents quickly and autonomously reach supracompetitive prices and profits."),
("multi-agent-safety-challenges","https://arxiv.org/abs/2402.07510","url","",
 "https://proceedings.neurips.cc/paper_files/paper/2024/hash/861f7dad098aec1c3560fb7add468d41-Abstract-Conference.html"),

# ---------------- reasoning-capabilities-understanding-lacking ----------------
("reasoning-capabilities-understanding-lacking","https://arxiv.org/abs/2405.00332","what",
 "some models scored up to 13% worse on it","several families of models scored up to 8% worse on it"),
("reasoning-capabilities-understanding-lacking","https://arxiv.org/abs/2405.00332","q","",
 "we observe accuracy drops of up to 8%, with several families of models showing evidence of systematic overfitting across almost all model sizes"),
("reasoning-capabilities-understanding-lacking","https://arxiv.org/abs/2410.05229","q","",
 "the performance of all models declines when only the numerical values in the question are altered"),

# ---------------- values-encoding-unclear ----------------
("values-encoding-unclear","https://www.anthropic.com/news/claudes-constitution","what",
 "Anthropic replaced the May 2023 constitution with a new document that not only instructs",
 "Anthropic announced it had replaced the May 2023 constitution with a new document that not only instructs"),

# ---------------- safety-performance-tradeoffs ----------------
("safety-performance-tradeoffs","https://arxiv.org/abs/2308.01263","url","","https://arxiv.org/html/2308.01263v3"),
("safety-performance-tradeoffs","https://arxiv.org/abs/2303.08774","url","","https://arxiv.org/html/2303.08774v6"),

# ---------------- drone-warfare ----------------
("drone-warfare","https://en.wikipedia.org/wiki/Operation_Spiderweb","what",
 "damaging or destroying dozens","damaging or destroying at least ten (Ukraine claimed far more)"),

# ---------------- ai-policing-surveillance ----------------
("ai-policing-surveillance","https://www.edpb.europa.eu/news/national-news/2022/facial-recognition-italian-sa-fines-clearview-ai","url","",
 "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9751362"),

# ---------------- emergent-capabilities ----------------
("emergent-capabilities","https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/","what",
 "month-long autonomous tasks by 2027-2031","month-long autonomous tasks before the end of this decade"),

# ---------------- overreliance-automation-bias ----------------
("overreliance-automation-bias","https://fortune.com/2025/10/07/deloitte-ai-australia-government-report-hallucinations","what",
 "~A$440,000","$290,000"),

# ---------------- military-predictive-analytics ----------------
("military-predictive-analytics","https://www.gao.gov/products/gao-20-665t","what",
 "a 2015 report said ~80% of ALIS-flagged issues were false positives",
 "GAO found squadron staff sometimes flew aircraft anyway because they distrusted the system's records"),

# ---------------- pretraining-misaligned-models ----------------
("pretraining-misaligned-models","https://alignment.anthropic.com/2025/pretraining-data-filtering","m",
 "Pretraining-data filtering can strip harmful (CBRN) knowledge out of a base model with",
 "Pretraining-data filtering measurably reduces harmful (CBRN) capability in a base model (33.7% to 30.8%, against a 25% random baseline) with"),

# ---------------- superalignment-time-pressure ----------------
("superalignment-time-pressure","https://arxiv.org/html/2503.14499v1","m",
 "about every 4 months for 2024-only models","about every three months for 2024-only models"),

# ---------------- test-set-contamination ----------------
("test-set-contamination","https://arxiv.org/abs/2405.00332","q",
 "accuracy drops of up to 13%","accuracy drops of up to 8%"),
("test-set-contamination","https://arxiv.org/abs/2405.00332","what",
 "13%","8%"),

# ---------------- unforeseen-capability-jumps ----------------
("unforeseen-capability-jumps","https://en.wikipedia.org/wiki/AlphaGo_versus_Lee_Sedol","what",
 "a fifth-line","an unconventional"),
]
