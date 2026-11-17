# LiminalGuard — Ubuntu et Raspberry Pi OS

![LiminalGuard](assets/liminalguard-logo.svg)

Installer AdGuard Home sur un Raspberry Pi, avec un compte personnel et sans historique des requêtes DNS.

Version **bêta 0.1.0-beta.1** pour Linux. Installation et DNS vérifiés sous WSL isolé et dans Raspberry Pi OS ARM64 sur un Pi 3B émulé, avec un client DNS séparé et un redémarrage du système. Voir [la validation](docs/validation.md).

La version Android est séparée : [LiminalGuard Android — expérimental, en cours de test](https://github.com/RZU-IT/LiminalGuard-Android). Ubuntu a été essayé sous WSL ; ces essais ne constituent pas une validation d’Ubuntu natif sur tous les PC.

## Installation

Raspberry Pi OS ou Debian 11+, systemd actif, Internet et accès sudo. Le Raspberry doit déjà être démarré. Extraire le paquet puis ouvrir son dossier dans le terminal ou par SSH :

```bash
sudo bash installer.sh
```

Choisir un mot de passe administrateur d’au moins 12 caractères. La saisie est masquée. Le reste de l’installation est automatique. L’affichage se limite au nom, au logo en caractères, à la version, aux crédits et à une barre de progression. Aucun menu à parcourir.

```bash
bash installer.sh --help
bash installer.sh --version
sudo bash installer.sh verify --json
```

Le résultat JSON indique l’adresse DNS et l’URL de l’interface. Le nom d’utilisateur est `admin`, modifiable avec `--username`. `--interface eth0` permet de choisir une carte réseau. `--color never` et `NO_COLOR=1` désactivent les couleurs. La commande `bash installer.sh --project` affiche [le dépôt Git](https://github.com/RZU-IT/LiminalGuard).

Le [guide client](CLIENT_README.md) explique les réglages de la box et du téléphone, PC ou de la console. L’installation sur le Raspberry ne redirige pas automatiquement le trafic des autres appareils.

## Périmètre

- Raspberry Pi OS / Debian 11+, ARMv7 ou ARM64 selon le système installé ; ARMv6 proposé pour les systèmes compatibles. Ubuntu amd64 sert aux essais sous WSL.
- AdGuard Home officiel v0.107.80, archive contrôlée par SHA-256 avant activation. Les sommes attendues sont épinglées dans le script.
- DNS sur l’IPv4 privée du Raspberry, port 53 UDP/TCP. Administration HTTP sur cette adresse, port 3000, protégée par bcrypt. Garder cette interface sur un réseau de confiance ; ne pas ouvrir ces ports sur Internet.
- Filtre publicitaire, protection contre les domaines dangereux et contrôle parental. `--allow-adult` désactive ce dernier.
- Historique DNS et statistiques désactivés. Petit journal de diagnostic avec rotation ; aucune promesse de fonctionnement sans fichier technique.
- Résolveurs amont AdGuard DNS et Quad9 en HTTPS. Les fournisseurs amont reçoivent les requêtes ; le filtrage ne rend pas la navigation anonyme.

Le script ne change pas le DNS de l’hôte, le pare-feu, le DHCP de la box ou les appareils. Il refuse une installation étrangère et les ports occupés. Un service systemd assure le démarrage automatique.

Le premier chargement des listes peut prendre du temps. L’installation attend leur disponibilité jusqu’à deux minutes et signale un échec si les vérifications ne passent pas.

## Maintenance

```bash
sudo bash installer.sh verify
sudo bash installer.sh repair
sudo bash installer.sh remove
```

`verify` contrôle le service, le filtrage, une résolution normale et la protection de l’interface. `repair` sauvegarde puis réapplique le profil en conservant le compte, les règles et les listes personnelles. `remove` retire le service et garde les données dans `/opt/AdGuardHome`. Remettre les appareils en DNS automatique avant de retirer le service.

La version AdGuard est figée. Le script refuse un binaire modifié ou mis à jour sans validation correspondante. Il ne met pas automatiquement à niveau une installation existante. Ne pas contourner la vérification d’intégrité. L’adresse du Raspberry doit être réservée dans la box pour rester stable.

Le filtrage DNS ne garantit pas le blocage des publicités intégrées aux vidéos YouTube, Twitch, Netflix ou Disney+. Un appareil utilisant son propre DNS chiffré peut contourner le filtre.

## Développement

Le script autonome contient le lancement Bash et le moteur Python. Les tests isolés et les outils de paquetage restent séparés dans `tests/` et `tools/`. Les contrôles et leurs limites sont dans [docs/validation.md](docs/validation.md).

Les identifiants internes `rzu-adguard-home.service` et `.rzu-installation.json` sont conservés pour la compatibilité des installations précédentes. Le nom public est LiminalGuard.

Le paquetage refuse les preuves dont l’empreinte ne correspond plus au script. Les anciennes preuves ne valident pas une nouvelle version.

## Crédits et licence

Développé par RZU Informatique avec l’assistance d’OpenAI Codex. Logo vectoriel dessiné par coordonnées, inspiré des portes et couloirs des backrooms.

Le script et les créations originales sont sous [licence MIT](LICENSE). Elle autorise la réutilisation, y compris commerciale, avec conservation de la licence et du copyright. AdGuard Home et les dépendances gardent leurs propres conditions : [NOTICE.txt](NOTICE.txt).

Projet indépendant, sans affiliation avec AdGuard.

[AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) · [Version épinglée](https://github.com/AdguardTeam/AdGuardHome/releases/tag/v0.107.80) · [Configuration officielle](https://adguard-dns.io/kb/adguard-home/configuration/)
