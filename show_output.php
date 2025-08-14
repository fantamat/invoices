<?php
/**
 * Invoice Output Viewer
 * 
 * This script displays the JSON outputs of invoice analysis models
 * based on the Invoice schema defined in invoice_types.py
 * 
 * PHP Version 7.0+
 */

// Set error reporting for development
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Base directory for output files
$baseDir = __DIR__ . '/data/outputs';

// Check if directory exists, if not try other common paths
if (!is_dir($baseDir)) {
    $baseDir = dirname(__DIR__) . '/data/outputs';
}
if (!is_dir($baseDir)) {
    $baseDir = __DIR__ . '/../data/outputs';
}
if (!is_dir($baseDir)) {
    $baseDir = 'd:/deymed/invoces/data/outputs';
}

// Get available models (directories)
function getAvailableModels() {
    global $baseDir;
    $models = [];
    
    if (is_dir($baseDir)) {
        $dirs = scandir($baseDir);
        foreach ($dirs as $dir) {
            if ($dir !== '.' && $dir !== '..' && is_dir($baseDir . '/' . $dir)) {
                $models[] = $dir;
            }
        }
    }
    
    return $models;
}

// Get available JSON files for a model
function getAvailableFiles($model) {
    global $baseDir;
    $files = [];
    
    $modelDir = $baseDir . '/' . $model;
    if (is_dir($modelDir)) {
        $dirFiles = scandir($modelDir);
        foreach ($dirFiles as $file) {
            if (pathinfo($file, PATHINFO_EXTENSION) === 'json' && is_file($modelDir . '/' . $file)) {
                $files[] = $file;
            }
        }
    }
    
    return $files;
}

// Read and parse JSON file
function readJsonFile($model, $file) {
    global $baseDir;
    $filePath = $baseDir . '/' . $model . '/' . $file;
    
    if (file_exists($filePath)) {
        try {
            $content = file_get_contents($filePath);
            if ($content === false) {
                error_log("Error reading file: $filePath");
                return null;
            }
            $data = json_decode($content, true);
            if (json_last_error() !== JSON_ERROR_NONE) {
                error_log("JSON parsing error in file $filePath: " . json_last_error_msg());
                return null;
            }
            if (isset($data['invoice'])) {
                return $data['invoice'];
            }
            return $data;
        } catch (Exception $e) {
            error_log("Exception reading JSON file: " . $e->getMessage());
            return null;
        }
    } else {
        error_log("File does not exist: $filePath");
    }
    
    return null;
}

// Format currency display
function formatCurrency($amount, $currency) {
    if (!is_numeric($amount)) {
        return $amount;
    }
    
    if ($currency === 'CZK') {
        return number_format((float)$amount, 2, ',', ' ') . ' Kč';
    } else if ($currency === 'EUR') {
        return '€' . number_format((float)$amount, 2, '.', ',');
    } else if ($currency === 'USD') {
        return '$' . number_format((float)$amount, 2, '.', ',');
    } else {
        return number_format((float)$amount, 2, '.', ',') . ' ' . $currency;
    }
}

// Handle form submission
$selectedModel = $_GET['model'] ?? '';
$selectedFile = $_GET['file'] ?? '';
$models = getAvailableModels();
$files = [];
$jsonData = null;

if ($selectedModel) {
    $files = getAvailableFiles($selectedModel);
    
    if ($selectedFile && in_array($selectedFile, $files)) {
        $jsonData = readJsonFile($selectedModel, $selectedFile);
    } else if (!empty($files)) {
        $selectedFile = $files[0];
        $jsonData = readJsonFile($selectedModel, $selectedFile);
    }
}
?>
<?php
// Debugging information - uncomment if needed
// echo '<pre>Base Directory: ' . $baseDir . '</pre>';
// echo '<pre>Is Directory: ' . (is_dir($baseDir) ? 'Yes' : 'No') . '</pre>';
// if (isset($selectedModel) && !empty($selectedModel)) {
//     echo '<pre>Model Directory: ' . $baseDir . '/' . $selectedModel . '</pre>';
//     echo '<pre>Is Model Directory: ' . (is_dir($baseDir . '/' . $selectedModel) ? 'Yes' : 'No') . '</pre>';
// }
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoice Output Viewer</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: #fff;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .selection-form {
            display: flex;
            margin-bottom: 20px;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        select, button {
            padding: 8px 12px;
            border-radius: 4px;
            border: 1px solid #ddd;
            font-size: 16px;
        }
        button {
            background-color: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
        }
        button:hover {
            background-color: #45a049;
        }
        .invoice-data {
            margin-top: 30px;
        }
        .section {
            margin-bottom: 20px;
            border: 1px solid #eee;
            padding: 15px;
            border-radius: 5px;
            background-color: #fafafa;
        }
        .section h2 {
            margin-top: 0;
            color: #333;
            font-size: 18px;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f2f2f2;
        }
        .info-row {
            display: flex;
            margin-bottom: 10px;
        }
        .info-label {
            font-weight: bold;
            width: 200px;
        }
        .info-value {
            flex-grow: 1;
        }
        .address {
            margin-left: 20px;
        }
        .error-message {
            color: #ff0000;
            background-color: #ffe6e6;
            padding: 10px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .processing-time {
            font-size: 12px;
            color: #666;
            margin-top: 20px;
            text-align: right;
            font-style: italic;
        }
        .json-raw {
            margin-top: 20px;
            padding: 15px;
            background-color: #f8f8f8;
            border: 1px solid #ddd;
            border-radius: 5px;
            overflow: auto;
            max-height: 500px;
        }
        pre {
            margin: 0;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Invoice Output Viewer</h1>
        
        <form class="selection-form" method="GET">
            <div>
                <label for="model">Select Model:</label>
                <select id="model" name="model" onchange="this.form.submit()">
                    <option value="">-- Select Model --</option>
                    <?php foreach ($models as $model): ?>
                        <option value="<?= htmlspecialchars($model) ?>" <?= $selectedModel === $model ? 'selected' : '' ?>>
                            <?= htmlspecialchars($model) ?>
                        </option>
                    <?php endforeach; ?>
                </select>
            </div>
            
            <?php if ($selectedModel): ?>
            <div>
                <label for="file">Select File:</label>
                <select id="file" name="file" onchange="this.form.submit()">
                    <option value="">-- Select File --</option>
                    <?php foreach ($files as $file): ?>
                        <option value="<?= htmlspecialchars($file) ?>" <?= $selectedFile === $file ? 'selected' : '' ?>>
                            <?= htmlspecialchars($file) ?>
                        </option>
                    <?php endforeach; ?>
                </select>
            </div>
            <?php endif; ?>
        </form>
        
        <?php if ($jsonData): ?>
        <div class="invoice-data">
            <h2>Invoice Details: <?= htmlspecialchars($selectedFile) ?></h2>
            
            <?php
            // Try to find and display original image if available
            $baseFileName = pathinfo($selectedFile, PATHINFO_FILENAME);
            $possibleImagePaths = [
                __DIR__ . '/data/png/' . $baseFileName . '.png',
                __DIR__ . '/data/invoices/png/' . $baseFileName . '.png', 
                dirname(__DIR__) . '/data/png/' . $baseFileName . '.png',
                'd:/deymed/invoces/data/png/' . $baseFileName . '.png'
            ];
            
            $imagePath = null;
            foreach ($possibleImagePaths as $path) {
                if (file_exists($path)) {
                    $imagePath = $path;
                    break;
                }
            }
            
            if ($imagePath): 
                // Convert to data URI for display without web server
                $imageData = @file_get_contents($imagePath);
                if ($imageData) {
                    $base64Image = base64_encode($imageData);
                    $imageType = pathinfo($imagePath, PATHINFO_EXTENSION);
                    $dataUri = 'data:image/' . $imageType . ';base64,' . $base64Image;
            ?>
            <div class="section">
                <h2>Original Invoice Image</h2>
                <img src="<?= $dataUri ?>" alt="Invoice Image" style="max-width: 100%; height: auto;">
            </div>
            <?php 
                }
            endif; 
            ?>
            
            <?php 
            // Try to display based on Invoice schema, but be flexible since JSON formats may vary
            ?>
            
            <?php if (isset($jsonData['type'])): ?>
            <div class="section">
                <h2>Invoice Information</h2>
                <div class="info-row">
                    <div class="info-label">Type:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['type']) ?></div>
                </div>
                
                <?php if (isset($jsonData['internal_invoice_number'])): ?>
                <div class="info-row">
                    <div class="info-label">Internal Invoice Number:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['internal_invoice_number']) ?></div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['external_invoice_number'])): ?>
                <div class="info-row">
                    <div class="info-label">External Invoice Number:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['external_invoice_number']) ?></div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['issue_date'])): ?>
                <div class="info-row">
                    <div class="info-label">Issue Date:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['issue_date']) ?></div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['due_date'])): ?>
                <div class="info-row">
                    <div class="info-label">Due Date:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['due_date']) ?></div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['payment_method'])): ?>
                <div class="info-row">
                    <div class="info-label">Payment Method:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['payment_method']) ?></div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['description'])): ?>
                <div class="info-row">
                    <div class="info-label">Description:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['description']) ?></div>
                </div>
                <?php endif; ?>
            </div>
            <?php endif; ?>
            
            <?php 
            // Company Information (own company) - Invoice format
            if (isset($jsonData['own_company_info'])): 
            ?>
            <div class="section">
                <h2>Own Company Information</h2>
                <div class="info-row">
                    <div class="info-label">Company Name:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['own_company_info']['company_name']) ?></div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Identification Number:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['own_company_info']['identification_number']) ?></div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Tax Number:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['own_company_info']['tax_number']) ?></div>
                </div>
                
                <?php if (isset($jsonData['own_company_info']['address'])): ?>
                <div class="info-row">
                    <div class="info-label">Address:</div>
                    <div class="info-value address">
                        <?= htmlspecialchars($jsonData['own_company_info']['address']['street']) ?><br>
                        <?= htmlspecialchars($jsonData['own_company_info']['address']['postalcode']) ?>
                        <?= htmlspecialchars($jsonData['own_company_info']['address']['city']) ?><br>
                        <?= htmlspecialchars($jsonData['own_company_info']['address']['country']) ?>
                    </div>
                </div>
                <?php endif; ?>
            </div>
            <?php endif; ?>
            
            <?php 
            // Counterparty Information - Invoice format
            if (isset($jsonData['counterparty_info'])): 
            ?>
            <div class="section">
                <h2>Counterparty Information</h2>
                <div class="info-row">
                    <div class="info-label">Company Name:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['counterparty_info']['company_name']) ?></div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Identification Number:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['counterparty_info']['identification_number']) ?></div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Tax Number:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['counterparty_info']['tax_number']) ?></div>
                </div>
                
                <?php if (isset($jsonData['counterparty_info']['address'])): ?>
                <div class="info-row">
                    <div class="info-label">Address:</div>
                    <div class="info-value address">
                        <?= htmlspecialchars($jsonData['counterparty_info']['address']['street']) ?><br>
                        <?= htmlspecialchars($jsonData['counterparty_info']['address']['postalcode']) ?>
                        <?= htmlspecialchars($jsonData['counterparty_info']['address']['city']) ?><br>
                        <?= htmlspecialchars($jsonData['counterparty_info']['address']['country']) ?>
                    </div>
                </div>
                <?php endif; ?>
            </div>
            <?php endif; ?>
            
            <?php 
            // Customer/Billing Account information (simpler format)
            if (isset($jsonData['customer']) || isset($jsonData['billing_account'])): 
            ?>
            <div class="section">
                <h2>Customer/Supplier Information</h2>
                
                <?php if (isset($jsonData['customer'])): ?>
                <div class="info-row">
                    <div class="info-label">Customer:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['customer']) ?></div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['billing_account'])): ?>
                <div class="info-row">
                    <div class="info-label">Supplier Name:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['billing_account']['account_name']) ?></div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Company ID:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['billing_account']['company_id']) ?></div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">VAT ID:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['billing_account']['vat_id']) ?></div>
                </div>
                
                <?php if (isset($jsonData['billing_account']['adress'])): ?>
                <div class="info-row">
                    <div class="info-label">Address:</div>
                    <div class="info-value address">
                        <?= htmlspecialchars($jsonData['billing_account']['adress']['street']) ?><br>
                        <?= htmlspecialchars($jsonData['billing_account']['adress']['postalcode']) ?>
                        <?= htmlspecialchars($jsonData['billing_account']['adress']['city']) ?><br>
                        <?= htmlspecialchars($jsonData['billing_account']['adress']['country']) ?>
                    </div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['billing_account']['account_phone'])): ?>
                <div class="info-row">
                    <div class="info-label">Phone:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['billing_account']['account_phone']) ?></div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['billing_account']['account_email'])): ?>
                <div class="info-row">
                    <div class="info-label">Email:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['billing_account']['account_email']) ?></div>
                </div>
                <?php endif; ?>
                <?php endif; ?>
            </div>
            <?php endif; ?>
            
            <?php
            // Banking Information - Invoice format
            if (isset($jsonData['banking_info'])): 
            ?>
            <div class="section">
                <h2>Banking Information</h2>
                <div class="info-row">
                    <div class="info-label">Account Number:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['banking_info']['account_number']) ?></div>
                </div>
                
                <div class="info-row">
                    <div class="info-label">Bank Code:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['banking_info']['bank_code']) ?></div>
                </div>
                
                <?php if (!empty($jsonData['banking_info']['iban'])): ?>
                <div class="info-row">
                    <div class="info-label">IBAN:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['banking_info']['iban']) ?></div>
                </div>
                <?php endif; ?>
                
                <?php if (!empty($jsonData['banking_info']['bic'])): ?>
                <div class="info-row">
                    <div class="info-label">BIC/SWIFT:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['banking_info']['bic']) ?></div>
                </div>
                <?php endif; ?>
            </div>
            <?php endif; ?>
            
            <?php 
            // Display amounts - handling both formats
            ?>
            <div class="section">
                <h2>Amount Information</h2>
                
                <?php if (isset($jsonData['amount'])): // Invoice format ?>
                <div class="info-row">
                    <div class="info-label">Total Amount:</div>
                    <div class="info-value">
                        <?= formatCurrency($jsonData['amount'], $jsonData['currency_id'] ?? '') ?>
                    </div>
                </div>
                
                <?php if (isset($jsonData['amount_wo_rounding'])): ?>
                <div class="info-row">
                    <div class="info-label">Amount Before Rounding:</div>
                    <div class="info-value">
                        <?= formatCurrency($jsonData['amount_wo_rounding'], $jsonData['currency_id'] ?? '') ?>
                    </div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['amount_rounding']) && $jsonData['amount_rounding'] != 0): ?>
                <div class="info-row">
                    <div class="info-label">Rounding Amount:</div>
                    <div class="info-value">
                        <?= formatCurrency($jsonData['amount_rounding'], $jsonData['currency_id'] ?? '') ?>
                    </div>
                </div>
                <?php endif; ?>
                
                <?php elseif (isset($jsonData['order_total_price'])): // Simple format ?>
                <div class="info-row">
                    <div class="info-label">Total Price:</div>
                    <div class="info-value">
                        <?= formatCurrency($jsonData['order_total_price'], $jsonData['order_currency'] ?? '') ?>
                    </div>
                </div>
                <?php endif; ?>
                
                <?php if (isset($jsonData['currency_id'])): ?>
                <div class="info-row">
                    <div class="info-label">Currency:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['currency_id']) ?></div>
                </div>
                <?php elseif (isset($jsonData['order_currency'])): ?>
                <div class="info-row">
                    <div class="info-label">Currency:</div>
                    <div class="info-value"><?= htmlspecialchars($jsonData['order_currency']) ?></div>
                </div>
                <?php endif; ?>
            </div>
            
            <?php 
            // Items - handle both formats
            if (isset($jsonData['items']) || isset($jsonData['lines'])): 
                $itemsArray = isset($jsonData['lines']) ? $jsonData['lines'] : $jsonData['items'];
            ?>
            <div class="section">
                <h2>Line Items</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Part Number</th>
                            <th>Description</th>
                            <th>Quantity</th>
                            <th>Unit Price</th>
                            <th>Total Price</th>
                            <?php if (isset($jsonData['lines'][0]['tax_class_id'])): ?>
                            <th>VAT %</th>
                            <th>Total with VAT</th>
                            <?php endif; ?>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($itemsArray as $item): ?>
                        <tr>
                            <td>
                                <?php 
                                if (isset($item['part_number'])) {
                                    echo htmlspecialchars($item['part_number']);
                                } elseif (isset($item['mfr_part_no'])) {
                                    echo htmlspecialchars($item['mfr_part_no']);
                                } elseif (isset($item['item_id'])) {
                                    echo htmlspecialchars($item['item_id']);
                                } else {
                                    echo '-';
                                }
                                ?>
                            </td>
                            <td>
                                <?php 
                                if (isset($item['description'])) {
                                    echo htmlspecialchars($item['description']);
                                } elseif (isset($item['name'])) {
                                    echo htmlspecialchars($item['name']);
                                } else {
                                    echo '-';
                                }
                                ?>
                            </td>
                            <td><?= htmlspecialchars($item['quantity']) ?></td>
                            <td>
                                <?php
                                $currency = '';
                                if (isset($jsonData['currency_id'])) {
                                    $currency = $jsonData['currency_id'];
                                } elseif (isset($jsonData['order_currency'])) {
                                    $currency = $jsonData['order_currency'];
                                }
                                
                                if (isset($item['unit_price'])) {
                                    echo formatCurrency($item['unit_price'], $currency);
                                } else {
                                    echo '-';
                                }
                                ?>
                            </td>
                            <td>
                                <?php
                                if (isset($item['total_price'])) {
                                    echo formatCurrency($item['total_price'], $currency);
                                } elseif (isset($item['ext_price'])) {
                                    echo formatCurrency($item['ext_price'], $currency);
                                } elseif (isset($item['price_without_vat'])) {
                                    echo formatCurrency($item['price_without_vat'], $currency);
                                } else {
                                    echo '-';
                                }
                                ?>
                            </td>
                            <?php if (isset($jsonData['lines'][0]['tax_class_id'])): ?>
                            <td><?= htmlspecialchars($item['tax_class_id']) ?>%</td>
                            <td>
                                <?php
                                if (isset($item['total_with_vat'])) {
                                    echo formatCurrency($item['total_with_vat'], $currency);
                                } elseif (isset($item['price_with_vat'])) {
                                    echo formatCurrency($item['price_with_vat'], $currency);
                                } else {
                                    echo '-';
                                }
                                ?>
                            </td>
                            <?php endif; ?>
                        </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
            <?php endif; ?>
            
            <?php if (isset($jsonData['time'])): ?>
            <div class="processing-time">
                Processing time: <?= number_format($jsonData['time'], 2) ?> ms
            </div>
            <?php endif; ?>
            
            <div class="section">
                <h2>Raw JSON Data</h2>
                <div class="json-raw">
                    <pre><?= json_encode($jsonData, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE) ?></pre>
                </div>
            </div>
        </div>
        <?php elseif ($selectedModel && empty($files)): ?>
        <div class="error-message">
            No JSON files found for the selected model.
        </div>
        <?php elseif ($selectedModel && $selectedFile): ?>
        <div class="error-message">
            Unable to read or parse the selected JSON file.
        </div>
        <?php endif; ?>
    </div>
</body>
</html>
