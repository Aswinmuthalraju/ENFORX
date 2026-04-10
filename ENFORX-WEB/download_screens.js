const https = require('https');
const fs = require('fs');
const path = require('path');

const screens = [
  {
    name: 'LandingPage.html',
    url: 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sXzZiYzU3MmM4NTkxOTQzZmRiYjJlZTI4MjA2MjQ4OGViEgsSBxDpg-mflAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzMTgwODExNDI1NTYxNTM2NTI5&filename=&opi=89354086'
  },
  {
    name: 'SetupWizard.html',
    url: 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sXzQ4Mjc1OGZkYTkzODQyODBiNWU1MWNhZDk1MjlkNDg1EgsSBxDpg-mflAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzMTgwODExNDI1NTYxNTM2NTI5&filename=&opi=89354086'
  },
  {
    name: 'PremiumControlConsole.html',
    url: 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sXzI1MmJiOTQxNjA1NzQzYjhiMjIyMTQ1NzA5NzlhY2E1EgsSBxDpg-mflAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzMTgwODExNDI1NTYxNTM2NTI5&filename=&opi=89354086'
  },
  {
    name: 'SystemConsole.html',
    url: 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sX2E1MWEyNGQ1MjU1ODRlNWVhOTYyNjBlYmI5OTVmMDcwEgsSBxDpg-mflAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzMTgwODExNDI1NTYxNTM2NTI5&filename=&opi=89354086'
  },
  {
    name: 'FinancialAIConsole.html',
    url: 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sXzBlMTc5NTEzYjhiZTRiZWY5MWNiMDBkNjQ4OWU1NzM4EgsSBxDpg-mflAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzMTgwODExNDI1NTYxNTM2NTI5&filename=&opi=89354086'
  },
  {
    name: 'ApplicationFlow.html',
    url: 'https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ7Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpaCiVodG1sXzBmMTUwZmExYTY3MTQ4YThhYTcyN2EzMTAxY2ZiZDNlEgsSBxDpg-mflAcYAZIBIwoKcHJvamVjdF9pZBIVQhMzMTgwODExNDI1NTYxNTM2NTI5&filename=&opi=89354086'
  }
];

const downloadDir = path.join(__dirname, 'raw_screens');
if (!fs.existsSync(downloadDir)) fs.mkdirSync(downloadDir);

screens.forEach(screen => {
  const filePath = path.join(downloadDir, screen.name);
  const file = fs.createWriteStream(filePath);
  
  https.get(screen.url, (response) => {
    if (response.statusCode !== 200) {
      console.error(`Failed to download ${screen.name}: Status ${response.statusCode}`);
      return;
    }
    response.pipe(file);
    file.on('finish', () => {
      file.close();
      console.log(`Downloaded ${screen.name}`);
    });
  }).on('error', (err) => {
    fs.unlink(filePath, () => {});
    console.error(`Error downloading ${screen.name}: ${err.message}`);
  });
});
