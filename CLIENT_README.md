# LiminalGuard Linux — Ubuntu / Raspberry Pi OS — bêta

![LiminalGuard](assets/liminalguard-logo.svg)

Installer AdGuard Home sur Raspberry Pi. Développé par RZU Informatique.

Version expérimentale : lire les limites avant de modifier les DNS de ses appareils.

## Démarrer

Raspberry Pi OS / Debian 11+, systemd actif et accès sudo sont nécessaires. Le Raspberry doit déjà être installé, allumé et connecté à Internet. Extraire tout le ZIP puis ouvrir son dossier dans le terminal ou par SSH :

```bash
sudo bash installer.sh
```

Choisir le mot de passe du compte **admin**, au moins 12 caractères. La saisie est masquée par des étoiles. Le programme affiche son identité et une barre de progression ; il n’y a pas de menu.

Après l’installation, obtenir l’adresse du Raspberry et l’URL de l’interface :

```bash
sudo bash installer.sh verify --json
```

L’interface se trouve sur `http://ADRESSE-DU-RASPBERRY:3000`. Utiliser le compte admin et le mot de passe choisi. Ne pas ouvrir les ports 53 ou 3000 sur Internet. Le script ne configure pas la box ou la console à distance.

## Activer le filtrage sur ses appareils

Réserver l’adresse IPv4 du Raspberry dans la box, pour éviter qu’elle change. Indiquer cette adresse comme DNS primaire des appareils ou dans les réglages DHCP de la box si elle le permet. La procédure dépend du modèle de box.

Sur PS5 : Paramètres → Réseau → Paramètres → Configurer la connexion Internet → connexion actuelle → Paramètres avancés → Paramètres DNS → Manuel.

Ne pas ajouter un serveur secondaire public pour ce scénario : les appareils pourraient contourner le filtre. Le Raspberry doit rester allumé. Pour revenir au fonctionnement habituel, remettre les DNS en **Automatique**.

## Maintenance

```bash
sudo bash installer.sh verify
sudo bash installer.sh repair
sudo bash installer.sh remove
```

`repair` conserve le compte et les règles personnelles. `remove` retire le service mais conserve les données. Remettre les appareils en DNS automatique avant de retirer le filtre ou d’éteindre le Raspberry.

En cas d’erreur, demander le diagnostic lisible par un outil :

```bash
sudo bash installer.sh verify --json
```

Consulter ce résultat avant de le publier : il peut contenir l’adresse locale et des chemins. Ne jamais transmettre son mot de passe ni son fichier AdGuardHome.yaml.

## À savoir

AdGuard Home est figé en **v0.107.80**. Une mise à jour ou modification du binaire est refusée par le contrôle d’intégrité. La mise à niveau automatique n’est pas fournie ; ne pas supprimer les contrôles pour contourner un refus.

Historique des requêtes et statistiques désactivés ; petit journal technique limité. Les résolveurs amont AdGuard DNS et Quad9 reçoivent les requêtes DNS. Le contrôle parental est activé ; `--allow-adult` permet de le désactiver lors de l’installation ou de la réparation.

Le DNS ne bloque pas toutes les publicités, notamment celles intégrées aux vidéos. Un appareil utilisant son propre DNS chiffré peut contourner le filtrage.

Cette version bêta a passé ses tests sous WSL et dans Raspberry Pi OS ARM64 sur un Pi 3B émulé : installation, réparation, désinstallation/réinstallation, client DNS séparé et service après redémarrage. L’émulation ne valide pas la carte SD, l’alimentation, le Wi-Fi ou les réglages de votre box.

Licence du script et du logo : **MIT**, voir LICENSE. AdGuard Home conserve sa propre licence, voir NOTICE.txt. LiminalGuard est indépendant d’AdGuard.
