# LiminalGuard Linux

![LiminalGuard](assets/liminalguard-logo.svg)

Installe AdGuard Home sur Raspberry Pi OS ou Debian avec systemd. Version bêta ; Ubuntu testé sous WSL.

## Installation

[Télécharger le paquet Linux](https://github.com/RZU-IT/LiminalGuard/releases/tag/v0.1.0-beta.1-linux.1), extraire le ZIP puis ouvrir son dossier :

```bash
sudo bash installer.sh
```

Choisir le mot de passe administrateur. L’installation configure le service et affiche les informations de connexion. Le [guide d’utilisation](CLIENT_README.md) explique comment utiliser ce DNS sur les autres appareils.

## Entretien

```bash
sudo bash installer.sh verify
sudo bash installer.sh repair
sudo bash installer.sh remove
```

AdGuard Home est épinglé en version 0.107.80. Les mises à niveau automatiques ne sont pas prises en charge. Garder l’interface d’administration sur le réseau local.

Le filtrage DNS ne bloque pas toutes les publicités vidéo. L’historique DNS et les statistiques sont désactivés ; un journal technique est conservé.

[Options et fonctionnement](docs/reference.md) · [Validation](docs/validation.md) · [Version Android](https://github.com/RZU-IT/LiminalGuard-Android)

Développé par RZU Informatique avec l’assistance d’OpenAI Codex. [Licence MIT](LICENSE). AdGuard Home conserve sa propre licence : [notices](NOTICE.txt).
