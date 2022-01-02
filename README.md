# qiita-sync

![pytest](https://github.com/wak109/qiita-sync/actions/workflows/pytest.yml/badge.svg)

qiita-sync can make Qiita synchronized with GitHub.

If an article is updated in GitHub repository, this update is also applied to Qiita.
The vise-versa is also possible.


## Get Started

### Requirement

- Qiita Account
- GitHub repository

### Preparation

#### Qiita Access Token

1. Generate your access token.

   1. Open [Qiita Account Applications](https://qiita.com/settings/applications)
   1. Click "Generate new token"
   1. Copy the access token displayed.

1. Create a file of your access token.
   Replace "Your-Access-Token" in the command below by the generated access token.

   ```bash
   echo "Your-Access-Token" > access_token.txt
   chmod 400 access_token.txt
   ```

1. Check if your access token is valid
 
   ```bash
   curl -sH "Authorization: Bearer $(cat access_token.txt)" https://qiita.com/api/v2/authenticated_user/items
   ```
#### GitHub Repository (Optional)



## Note

- Supported version is 3.7 or newer because "future feature annotations is not defined" in 3.6
