import { Page, Locator } from '@playwright/test';

export class GeneratorPage {
  readonly page: Page;
  readonly autoTopicToggle: Locator;
  readonly topicInput: Locator;
  readonly includeLeadMagnetToggle: Locator;
  readonly generateBtn: Locator;
  readonly leadMagnetsContainer: Locator;
  readonly leadMagnetsList: Locator;
  readonly captionPreview: Locator;
  readonly processingStatus: Locator;

  constructor(page: Page) {
    this.page = page;
    this.autoTopicToggle = page.locator('#auto-topic-toggle');
    this.topicInput = page.locator('#topic');
    this.includeLeadMagnetToggle = page.locator('#include-lead-magnet');
    this.generateBtn = page.locator('#submit-btn');
    this.leadMagnetsContainer = page.locator('#lead-magnets-container');
    this.leadMagnetsList = page.locator('#lead-magnets-list');
    this.captionPreview = page.locator('#caption-preview');
    this.processingStatus = page.locator('#status-text');
  }

  async goto() {
    await this.page.goto('/');
    await this.page.waitForLoadState('networkidle');
  }

  async toggleAutoTopic() {
    await this.autoTopicToggle.evaluate((el: HTMLInputElement) => {
      if (!el.checked) el.click();
    });
  }

  async toggleLeadMagnet() {
    await this.includeLeadMagnetToggle.evaluate((el: HTMLInputElement) => {
      if (!el.checked) el.click();
    });
  }

  async setTopic(topic: string) {
    await this.topicInput.fill(topic);
  }

  async generate() {
    await this.generateBtn.evaluate((el: HTMLElement) => el.click());
  }

  async waitForGenerationComplete(timeoutMs = 120000) {
    await this.generateBtn.waitFor({ state: 'visible', timeout: timeoutMs });
    await this.captionPreview.waitFor({ state: 'visible' });
  }
}
