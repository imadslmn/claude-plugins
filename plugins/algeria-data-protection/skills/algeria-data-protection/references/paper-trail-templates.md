# Paper trail templates (`compliance/` folder)

Copy these into every project at scaffolding time and fill them as features are built. They are in
French because that is what the client's DPO and the ANPDP will read; keep the engineering notes in
English if you prefer, but the headings and the register must stay in French.

Generate `DATA-FLOWS.md` from `ai_gateway/tasks.yaml` where possible so documentation cannot drift
from code.

---

## 1. `REGISTRE-DES-TRAITEMENTS.md`

```markdown
# Registre des activités de traitement — <Projet>

**Responsable du traitement** : <Client>, <adresse>, RC <…>, représenté par <…>
**Délégué à la protection des données (DPO)** : <nom, fonction, email, téléphone>
**Sous-traitant** : Solrus (Imad <…>), Alger — contact protection des données : <email>
**Hébergement** : <prestataire>, datacenter <ville>, Algérie
**Dernière mise à jour** : AAAA-MM-JJ — **Version** : x.y

## Traitement T1 — <intitulé, ex. Gestion des commandes clients>
| Champ | Valeur |
|---|---|
| Finalité(s) | … |
| Base juridique | Consentement exprès / exécution du contrat / obligation légale (art. 7) |
| Personnes concernées | Clients, employés, enfants et parents, candidats… |
| Catégories de données | Identité, coordonnées, données bancaires, localisation, données sensibles : <aucune / préciser> |
| Source des données | Personne concernée / client / partenaire |
| Destinataires internes | Service X, Y |
| Sous-traitants | Solrus (développement, maintenance) ; <hébergeur> ; <relais SMS> |
| Transfert hors Algérie | Non / Oui → voir DATA-FLOWS.md flux F… ; fondement : … ; autorisation ANPDP n°… |
| Durée de conservation | Voir RETENTION.md |
| Mesures de sécurité | Voir SECURITY-MEASURES.md |
| Formalité ANPDP | Déclaration n°… du … / Autorisation n°… du … |
| Étude d'impact | Non requise / DPIA.md |
| Droits des personnes | Accès, rectification, opposition, suppression via <canal> ; délai de réponse : <j> |

## Traitement T2 — …
```

Add one block per purpose, not per table. A chatbot, an invoice extractor and a CRM are three
treatments even if they share a database.

---

## 2. `DATA-FLOWS.md`

```markdown
# Cartographie des flux sortants — <Projet>

Chaque ligne = un flux de données quittant l'infrastructure algérienne du projet.
Décision selon l'arbre du skill `algeria-data-protection`.

| Flux | Destination | Pays | Contenu envoyé | Données personnelles ? | Décision | Fondement / autorisation | Garanties |
|---|---|---|---|---|---|---|---|
| F1 — extraction factures | API <fournisseur IA> | US | Texte OCR anonymisé, classes de jetons : ORG, PHONE | Non (jetons uniquement) | Passerelle, dé-identifié | n/a — aucun transfert de données identifiantes | ZDR contractuel, DPA signé, chiffrement TLS, journal d'audit |
| F2 — scoring candidats | API <fournisseur IA> | US | Profil dé-identifié : identifiant de substitution, expérience, langues, wilaya, dernier poste — sans nom, contact, date de naissance ni photo | Non (vue dé-identifiée) | Passerelle, redesign « substitut + attributs » | n/a — aucun transfert de données identifiantes | ZDR contractuel, DPA signé, assertion d'egress |
| F3 — notifications WhatsApp | Meta (WhatsApp Business API) | IE/US | Numéro, prénom, texte du message | Oui | Exception | Contact initié par l'utilisateur ; exécution du contrat ; mention dans la politique de confidentialité | Minimisation du contenu |
| F4 — sauvegardes | <hébergeur> | DZ | Base complète chiffrée | Oui | Résidence | Aucun transfert | AES-256, clés en Algérie |

**Flux refusés / désactivés** : <liste des flux qui attendent une autorisation ANPDP, avec le feature flag>
**Interdit sur ce projet** : envoi de scans d'identité, photos, enregistrements vocaux, données de santé à tout service hors Algérie.
```

---

## 3. `RETENTION.md`

```markdown
| Catégorie | Durée | Déclencheur | Mécanisme de suppression | Sauvegardes |
|---|---|---|---|---|
| Comptes clients | Durée du contrat + 2 ans | Résiliation | Job nightly `purge_accounts` | Purgées sous 30 j |
| Journaux applicatifs | 90 jours | Rotation | logrotate | — |
| Journal passerelle IA (métadonnées) | 12 mois | Rotation | — | — |
| Mappings placeholders (Redis) | 10 minutes | TTL | expiration automatique | jamais sauvegardés |
| Candidatures non retenues | 6 mois | Décision | purge | — |
| Données enfants (crèche) | Durée d'inscription + 1 an | Départ | purge + confirmation parents | — |
```

---

## 4. `SECURITY-MEASURES.md` (headings to fill)

Hébergement et réseau (localisation, pare-feu, accès SSH par clés, VPN admin) · Chiffrement (TLS en
transit, chiffrement au repos des volumes et sauvegardes, gestion des clés en Algérie) · Contrôle
d'accès (RBAC, MFA back-office, revue trimestrielle des comptes) · Journalisation (ce qui est
journalisé, ce qui ne l'est jamais : prompts bruts, données bancaires) · Passerelle IA (redaction,
assertion d'egress, kill switch, versions) · Environnements (prod/staging séparés, données
synthétiques en dev) · Sous-traitants (liste, DPA, localisation) · Sauvegardes (fréquence, lieu,
test de restauration) · Gestion des vulnérabilités (mises à jour, dépendances, pentest) ·
Sensibilisation (confidentialité du personnel, clause de confidentialité dans les contrats).

---

## 5. `BREACH-PROCEDURE.md`

```markdown
1. Détection → ouvrir un incident (qui, quand, quoi), couper le flux concerné (AI_EGRESS_ENABLED=false si la passerelle est impliquée).
2. Qualification sous 24 h : données concernées, nombre de personnes, cause, risque pour les personnes.
3. Notification à l'ANPDP par le responsable du traitement dans le délai légal (délai court — vérifier le chiffre en vigueur dans le JO ; viser 72 h) : formulaire ANPDP + description, catégories et volume, conséquences probables, mesures prises.
4. Information des personnes concernées si risque élevé (canal, modèle de message).
5. Registre des violations : entrée datée, même pour les incidents non notifiés, avec justification.
6. Post-mortem et correctifs ; mise à jour de SECURITY-MEASURES.md.
Contacts : DPO client <…> ; Solrus <…> ; hébergeur <…>.
```

---

## 6. `DPIA.md` (only when required)

Description du traitement et des finalités · Nécessité et proportionnalité · Risques pour les
personnes (accès illégitime, modification, disparition) avec vraisemblance/gravité · Mesures
existantes et prévues · Avis du DPO · Décision du responsable du traitement · Date de revue.

Trigger it for: profilage (scoring, recommandation, détection de fraude), données sensibles,
surveillance systématique (pointage géolocalisé, caméras), enfants, croisement de fichiers,
traitement à grande échelle.

---

## 7. `privacy-policy.fr.md` skeleton

```markdown
# Politique de protection des données à caractère personnel — <Produit>
Responsable du traitement · Données collectées et finalités · Base juridique · Destinataires et
sous-traitants (dont : « certains traitements automatisés font appel à des services d'intelligence
artificielle de prestataires situés hors d'Algérie ; ces prestataires ne reçoivent que des contenus
dépourvus de toute donnée identifiante, ne conservent aucune donnée et n'en utilisent aucune à des
fins d'entraînement ») · Transferts hors Algérie (lister les flux de DATA-FLOWS.md avec décision
« exception » ou « autorisation ») · Durées de conservation · Sécurité · Vos droits (accès,
rectification, opposition, suppression) et comment les exercer, délai de réponse · Réclamation
auprès de l'ANPDP (www.anpdp.dz) · DPO : contact · Date de mise à jour.
```

Publish an Arabic version alongside. Link it from the app, the website footer and the WhatsApp
welcome message.

---

## 8. `consent-copy.md`

Exact strings for each collection point, e.g.:

- Inscription : « En créant un compte, j'accepte que <Client> traite mes données (identité,
  coordonnées) pour <finalité>, conformément à la politique de protection des données. »
- Transfert (only if a flow is on the "exception: consent" branch) : « J'accepte expressément que
  <données> soient transmises à <prestataire> situé en/aux <pays> afin de <finalité>. Je peux retirer
  ce consentement à tout moment via <canal>. » — stored with timestamp, version, IP.
- Chatbot WhatsApp : welcome message naming the controller, the AI nature of the assistant, the
  privacy policy link and how to reach a human.

---

## 9. Data-processing annex for Solrus proposals and contracts (`ANNEXE — Protection des données`)

```markdown
1. Rôles : le Client est responsable du traitement ; Solrus est sous-traitant au sens de la loi 18-07 modifiée.
2. Objet et durée du traitement sous-traité ; catégories de données et de personnes.
3. Instructions : Solrus ne traite les données que sur instruction documentée du Client.
4. Localisation : hébergement et traitement en Algérie ; tout appel à un prestataire étranger passe par la passerelle de dé-identification décrite en annexe technique ; aucune donnée identifiante n'est transmise hors Algérie sans décision écrite du Client et formalité ANPDP préalable.
5. Sous-traitants ultérieurs : liste annexée (hébergeur, prestataire IA, relais SMS) ; information préalable du Client pour tout ajout.
6. Sécurité : mesures de SECURITY-MEASURES.md ; confidentialité du personnel Solrus.
7. Violations : Solrus notifie le Client sans délai injustifié (objectif 24 h) avec les éléments nécessaires à la notification ANPDP.
8. Assistance : Solrus assiste le Client pour les droits des personnes, la DPIA, les déclarations/autorisations ANPDP (annexes techniques).
9. Fin de contrat : restitution puis suppression des données et sauvegardes sous <30> jours, attestation écrite.
10. Audit : le Client ou son DPO peut auditer la conformité une fois par an sur préavis raisonnable.
11. Formalités ANPDP : à la charge du Client ; Solrus fournit la cartographie des flux et la description des mesures ; toute fonctionnalité nécessitant une autorisation ANPDP est livrée désactivée jusqu'à réception de celle-ci et son délai n'est pas imputable à Solrus.
```

Clause 11 protects the payment schedule: the "end of development" milestone must not depend on the
ANPDP's response time.
