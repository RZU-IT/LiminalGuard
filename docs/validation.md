# Validation — 0.1.0-beta.1

Vérifications du 16 novembre 2026. Elles décrivent cette version ; elles ne garantissent pas l’absence de défauts sur tous les appareils.

## Essais réussis

- Syntaxes Bash et Python valides ; ShellCheck sans diagnostic.
- Six tests de revue : aide/version sans installation, arguments invalides refusés avant APT, sorties couleur/JSON, profil source conservé, configurations et marqueurs invalides signalés.
- Vingt-deux tests d’intégration dans un espace réseau privé : installation, résolution DNS TCP/UDP, blocage, interface protégée, réparation, retrait/reprise, téléchargement de liste retardé de 25 secondes, refus des ports occupés, des installations étrangères, des binaires altérés et des listes absentes.
- Vrais binaires officiels amd64, ARMv7, ARM64 et ARMv6 exécutés. Les variantes ARM ont été lancées sous QEMU.
- Service systemd temporaire isolé : installation, vérification, réparation, retrait et réinstallation.
- Session interactive réelle en pseudo-terminal : un seul mot de passe, masqué, conservé intégralement ; couleurs et présentation sur 40 colonnes.
- Sept tests de saisie : UTF-8, collage, retour arrière, dépassement de taille, absence d’écho en clair et restauration du terminal après Ctrl+C ou SIGTERM.
- Résolveurs HTTPS réels AdGuard DNS et Quad9 : résolution et contrôle parental vérifiés sur loopback, ports de test dédiés.
- Raspberry Pi OS Lite ARM64 du 6 octobre 2026 démarré sur le modèle QEMU `raspi3b`, avec le noyau Raspberry Pi 6.18.50 et un service systemd réel. Installation normale sans `--test-mode`, compte et règles conservés pendant la réparation, retrait/réinstallation, puis service et DNS après redémarrage.
- Client WSL séparé relié au Pi émulé par le réseau NAT QEMU : résolution normale, blocage UDP/TCP, classification par la liste officielle, API protégée et statistiques désactivées.

Le DNS de l’hôte n’a pas été modifié. Les tests systemd emploient un service temporaire et un espace réseau privé. Les comptes et mots de passe des tests sont temporaires et ne sont pas des identifiants de production.

Les fichiers JSON dans `preuves/` contiennent l’empreinte du script réellement testé. Le paquetage refuse une preuve manquante, échouée ou périmée.

## Correction locale après l’essai Raspberry Pi OS

Le chargement initial de la liste officielle dépassait l’ancienne attente d’environ 20 secondes dans le Pi émulé. Le service démarrait mais l’installation échouait à la vérification. L’attente utilise maintenant une échéance monotone de deux minutes ; une liste absente provoque toujours un échec. Le nouveau test de téléchargement lent et les essais Raspberry Pi OS ont passé avec cette correction. Cette correction est incluse dans le paquet Linux actualisé du 17 novembre 2026, publié sous le tag de paquetage `v0.1.0-beta.1-linux.1`. La version interne de l’installateur reste `0.1.0-beta.1` ; le suffixe distingue cette révision de distribution sans modifier le script testé.

## Environnement et limites

Ubuntu sous WSL2 et Raspberry Pi OS Lite ARM64 sous QEMU 8.2.2, modèle Pi 3B/Cortex-A53, quatre cœurs et 1 Gio. L’image officielle a été vérifiée par SHA-256. La VM utilise une interface Ethernet USB émulée, un profil DHCP préconfiguré et une horloge initiale fournie au système invité. Le watchdog matériel est désactivé dans cette VM pour éviter un redémarrage prématuré de QEMU ; cloud-init et le gestionnaire réseau inutilisé sont désactivés après provisionnement. Ces adaptations concernent l’environnement de test, pas l’installateur.

Les contrôles après redémarrage attendent la disponibilité du service avant les requêtes du client. Un premier contrôle lancé trop tôt a expiré ; cet essai est conservé dans les preuves. L’émulation ne vérifie pas la carte SD, l’alimentation, le Wi-Fi, la box ou les réglages DNS d’un appareil physique.

La compatibilité avec d’autres distributions n’est pas établie. Les pannes de courant, carte SD, box ou connexion Internet ne sont pas couvertes par ces essais. Le contrôle parental est un filtrage DNS de domaines, pas une analyse des contenus des applications. Aucun blocage universel des publicités vidéo n’est annoncé.

L’administration HTTP doit rester sur un réseau local de confiance. Le script n’est pas un mécanisme de mise à niveau automatique : la version AdGuard reste épinglée.

## Reproduire les essais Linux

Sur une machine de développement adaptée, pas sur une machine de production :

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-yaml python3-bcrypt iproute2 qemu-user-static shellcheck
python3 tests/review.py
sudo python3 tests/prepare_assets.py
sudo unshare --net -- bash -c 'ip link set lo up; python3 tests/integration.py'
sudo unshare --net -- bash -c 'ip link set lo up; python3 tests/interactive_prompt.py'
sudo python3 tests/masked_input.py
sudo python3 tests/live_upstreams.py
```

Ces commandes ne sont pas nécessaires pour utiliser le paquet client. Le test réseau public contacte des résolveurs externes et n’écoute que sur loopback. Les mots de passe présents dans les tests sont des données temporaires de test, pas des identifiants de production.

Après réussite, `python3 tools/package.py` produit `.distribution/LiminalGuard.zip`. Le paquetage vérifie la correspondance des preuves avec le script et refuse des preuves périmées.
