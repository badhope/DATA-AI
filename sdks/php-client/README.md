# DATA-AI · PHP SDK

Minimal Guzzle-based client for the DATA-AI HTTP API.

## Requirements

- PHP 7.2 or later
- `guzzlehttp/guzzle` ^7.9

## Usage

```php
require 'vendor/autoload.php';

use DataAi\Client;

$client = new Client([
    'base_url' => 'http://localhost:5001',
    'api_key'  => getenv('DATA_AI_KEY'),
]);

$response = $client->chat()->send([
    'app_id' => '<your-app-id>',
    'input'  => ['question' => 'What was Q4 revenue?'],
]);
```

If you want to try the example, `composer install` from this directory. To drop it into an existing project, copy `data-client.php` and add the `guzzlehttp/guzzle` requirement to your `composer.json`.
