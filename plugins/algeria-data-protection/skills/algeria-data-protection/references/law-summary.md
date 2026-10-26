# Law 18-07 (as amended by Law 25-11) — working summary for engineers

Read this when you need to explain *why* a rule in SKILL.md exists, draft a data-protection section for
a client, or decide which branch of the decision tree a flow lands in. Article numbers marked (v) should
be verified against the Journal Officiel (Loi 18-07, JO n°34 of 10 June 2018; Loi 25-11, JO n°48 of
July 2025) before being quoted to a client or regulator. This is a summary by a non-lawyer.

## Scope

- Applies to any processing of personal data of natural persons by public or private bodies, by
  automated means or not, when the controller is established in Algeria **or** uses processing means
  located in Algeria (a foreign controller then needs a local representative). (art. 3 (v))
- Excluded: purely personal/household activities; data relating to national defence and security
  (exclusion added by 25-11). (art. 6)
- Personal data = any information relating to an identified or identifiable natural person. 25-11
  added definitions of biometric data, profiling, pseudonymization, and data breach. Pseudonymized data
  remains personal data.
- Sensitive data = data revealing racial/ethnic origin, political opinions, religious/philosophical
  beliefs, union membership, health, genetic, biometric, sexual life, offences/convictions. Processing
  is prohibited unless an exception applies and ANPDP authorization is obtained. (art. 18 (v))

## Lawful basis and consent

- Default basis is the **express consent** of the data subject (art. 7). Consent must be informed and
  can be withdrawn. Exceptions where consent is not required: legal obligation, performance of a
  contract to which the subject is party, protection of vital interests, public-interest task,
  legitimate interest of the controller balanced against the subject's rights (narrower than GDPR in
  practice; do not rely on it for AI processing without legal review).
- Information to provide at collection (art. 32–33 (v)): identity of the controller, purposes,
  recipients, mandatory/optional nature, rights of access/rectification/opposition, and **whether
  data will be transferred abroad**. If an AI provider abroad receives even de-identified derivatives,
  the safer practice is to say so in the privacy notice in plain language.

## Formalities with the ANPDP

- **Declaration** (art. 12): every processing operation is declared beforehand via the ANPDP portal
  (anpdp.dz) by the controller. No waiting period, but the receipt must exist before processing starts.
- **Authorization** (art. 12 and 18 (v)): required instead of declaration for sensitive data,
  interconnection of files with different purposes (art. 19), processing involving NIN-type
  identifiers in some cases, and **transfers to non-adequate countries** (art. 44–45, 45 bis).
  Processing may not begin before the written authorization.
- **Interconnection** (art. 19): linking files held for different purposes or by different bodies
  needs authorization — relevant for ERP + external CRM + chatbot stacks that join datasets.

## Cross-border transfers (the part that matters for foreign AI APIs)

- Principle (art. 44): a transfer to a foreign state is allowed only if that state ensures an adequate
  level of protection, as assessed by the ANPDP. No public adequacy list existed as of late 2026;
  treat every destination as non-adequate.
- Exceptions (art. 45): the ANPDP may authorize a transfer to a non-adequate country; transfers may
  also take place without that authorization when the data subject has **expressly consented** to the
  transfer, or when the transfer is necessary for: performance of a contract between subject and
  controller (or pre-contractual measures at the subject's request); a contract in the subject's
  interest between controller and a third party; protection of the subject's vital interests; a legal
  obligation; the establishment/exercise/defence of legal claims. Controllers may also obtain
  authorization by offering sufficient safeguards, notably contractual clauses. (v — the exact list
  and whether consent alone suffices without notification has varied in commentary; confirm.)
- 25-11 added articles 45 bis 1 to 45 bis 14 detailing adequacy assessment criteria, the content of
  authorization requests, onward-transfer limits (data received from abroad may not be re-transferred
  without the sender's agreement — 45 bis 14), retention of transferred data for the agreed period
  only, and an absolute prohibition on transfers that endanger state security or vital national
  interests (undefined; interpreted broadly).
- Operational consequence: a request body sent to a foreign LLM API containing personal data is a
  transfer, whatever the provider does with it afterward. ZDR, encryption in transit, and a signed DPA
  are *safeguards* to cite in a dossier; they do not replace the authorization or exception.
- The transfer regime is not triggered by content that contains no personal data. Hence the gateway.

## Obligations added or sharpened by 25-11

- **Delegate (DPO)**: designation of a délégué à la protection des données by controllers in the cases
  the law lists (art. 38 / 41 bis (v)); the ANPDP has publicly asked all operators to formalize one.
  In practice: the client names a DPO; Solrus names an internal contact for processor obligations.
- **Register of processing activities** for controllers *and processors*, including an automated log
  (carnet) of operations on the data (collection → deletion). Solrus must keep its own processor
  register per client project.
- **DPIA** (étude d'impact) before high-risk processing: profiling, sensitive data, large scale,
  systematic monitoring (geolocated attendance, camera analytics), children.
- **Breach notification** to the ANPDP within a short statutory deadline (commentary cites 72 hours
  or 5 days — confirm the figure in the JO), and to data subjects when the breach is likely to affect
  them. Have the procedure written before it is needed.
- **Processor contract**: written contract between controller and processor fixing purpose, data
  categories, security measures, sub-processing, breach notification, return/deletion at end.
  Sub-processors (the AI provider, hosting, SMS relay) must be covered.
- **Security** (art. 38–40 (v)): technical and organisational measures proportionate to risk;
  confidentiality obligations on staff; the controller chooses processors offering sufficient
  guarantees.
- **ANPDP powers**: regional audit/inspection poles (art. 27 bis), field inspections of private
  companies running since 2024, administrative sanctions (warning, formal notice, suspension or
  withdrawal of authorization) in addition to criminal penalties (art. 47–74: fines DZD 20,000 to
  1,000,000 and 2 months to 5 years' imprisonment, with aggravations for sensitive data and illegal
  transfers).

## Data-subject rights to implement in every product

Access, rectification, opposition (including to profiling/direct marketing), deletion where processing
is unlawful or purpose exhausted, and information about transfers. Build an endpoint or back-office
action for each; log the handling. Response deadlines are short — design for days.

## How to describe the Solrus architecture to a client or the ANPDP (FR)

> Les données à caractère personnel sont hébergées et traitées exclusivement sur des serveurs situés en
> Algérie. Les appels aux services d'intelligence artificielle de prestataires étrangers sont effectués
> via une passerelle unique qui supprime ou remplace par des jetons toute donnée identifiante avant
> l'envoi, et restaure ces données uniquement sur le serveur algérien à la réception. Le prestataire
> étranger ne reçoit donc aucune donnée permettant d'identifier une personne, n'en conserve aucune
> (politique de non-conservation contractuelle) et n'en utilise aucune à des fins d'entraînement.
> Les traitements nécessitant l'identité de la personne sont réalisés par des modèles hébergés en
> Algérie. Le registre des traitements, la cartographie des flux et les mesures de sécurité sont tenus
> à jour dans la documentation du projet.

Adapt this per project; never claim it if the code does not actually enforce it.
