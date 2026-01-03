import websiteInfoData from '../data/websiteinfo.json';
import certificationsData from '../data/certifications.json';
import productInfoData from '../data/productinfo.json';

const certItemsEn = certificationsData.reduce((acc, item) => {
  acc[item.key] = {
    title: item.title,
    desc: item.desc.en,
  };
  return acc;
}, {} as Record<string, { title: string; desc: string }>);

const certItemsZh = certificationsData.reduce((acc, item) => {
  acc[item.key] = {
    title: item.title,
    desc: item.desc.zh,
  };
  return acc;
}, {} as Record<string, { title: string; desc: string }>);

const productCategoriesEn = productInfoData.categories.reduce((acc, item) => {
  acc[item.key] = item.name.en;
  return acc;
}, {} as Record<string, string>);

const productCategoriesZh = productInfoData.categories.reduce((acc, item) => {
  acc[item.key] = item.name.zh;
  return acc;
}, {} as Record<string, string>);

const productCollectionsEn = productInfoData.collections.reduce((acc, item) => {
  acc[item.key] = item.name.en;
  return acc;
}, {} as Record<string, string>);

const productCollectionsZh = productInfoData.collections.reduce((acc, item) => {
  acc[item.key] = item.name.zh;
  return acc;
}, {} as Record<string, string>);

// Helper to extract nested translations
const getTranslation = (obj: any, lang: 'en' | 'zh', key?: string) => {
  if (!obj) return '';
  if (key && obj[key]) {
     return obj[key][lang];
  }
  return obj[lang];
};

export const translations = {
  en: {
    companyName: websiteInfoData.companyName.en,
    languages: [
      { code: 'en', label: 'EN', name: 'English' },
      { code: 'zh', label: 'CN', name: '中文' },
    ],
    nav: {
      productSearch: websiteInfoData.nav.productSearch.en,
      home: websiteInfoData.nav.home.en,
      about: websiteInfoData.nav.about.en,
      products: websiteInfoData.nav.products.en,
      services: websiteInfoData.nav.services.en,
      contact: websiteInfoData.nav.contact.en,
    },
    hero: {
      title: websiteInfoData.hero.title.en,
      subtitle: websiteInfoData.hero.subtitle.en,
      cta: websiteInfoData.hero.cta.en,
      contact: websiteInfoData.hero.contact.en,
      slides: {
        slide1: {
          title: websiteInfoData.hero.slides.slide1.title.en,
          subtitle: websiteInfoData.hero.slides.slide1.subtitle.en,
        },
        slide2: {
          title: websiteInfoData.hero.slides.slide2.title.en,
          subtitle: websiteInfoData.hero.slides.slide2.subtitle.en,
        },
        slide3: {
          title: websiteInfoData.hero.slides.slide3.title.en,
          subtitle: websiteInfoData.hero.slides.slide3.subtitle.en,
        },
        slide4: {
          title: websiteInfoData.hero.slides.slide4.title.en,
          subtitle: websiteInfoData.hero.slides.slide4.subtitle.en,
        }
      }
    },
    about: {
      title: websiteInfoData.about.title.en,
      description: websiteInfoData.about.description.en,
      mission: websiteInfoData.about.mission.en,
      imageDesc: websiteInfoData.about.imageDesc.en,
      stats: {
        years: websiteInfoData.about.stats.years.en,
        markets: websiteInfoData.about.stats.markets.en,
        quality: websiteInfoData.about.stats.quality.en,
      }
    },
    facility: {
      title: websiteInfoData.facility.title.en,
      subtitle: websiteInfoData.facility.subtitle.en,
      features: {
        capacity: {
          title: websiteInfoData.facility.features.capacity.title.en,
          desc: websiteInfoData.facility.features.capacity.desc.en,
        },
        machinery: {
          title: websiteInfoData.facility.features.machinery.title.en,
          desc: websiteInfoData.facility.features.machinery.desc.en,
        },
        inspection: {
          title: websiteInfoData.facility.features.inspection.title.en,
          desc: websiteInfoData.facility.features.inspection.desc.en,
        },
      }
    },
    certifications: {
      title: websiteInfoData.certifications.title.en,
      subtitle: websiteInfoData.certifications.subtitle.en,
      items: certItemsEn
    },
    brands: {
      title: websiteInfoData.brands.title.en,
      subtitle: websiteInfoData.brands.subtitle.en,
      list: websiteInfoData.brands.list.en
    },
    samples: {
      title: websiteInfoData.samples.title.en,
      subtitle: websiteInfoData.samples.subtitle.en,
      viewAll: websiteInfoData.samples.viewAll.en,
      galleryTitle: websiteInfoData.samples.galleryTitle.en
    },
    products: {
      title: websiteInfoData.products.title.en,
      subtitle: websiteInfoData.products.subtitle.en,
      searchButton: websiteInfoData.products.searchButton.en,
      backToCategories: websiteInfoData.products.backToCategories.en,
      backTo: websiteInfoData.products.backTo.en,
      viewDetails: websiteInfoData.products.viewDetails.en,
      inquire: websiteInfoData.products.inquire.en,
      searchPlaceholder: websiteInfoData.products.searchPlaceholder.en,
      showMore: websiteInfoData.products.showMore.en,
      showLess: websiteInfoData.products.showLess.en,
      selectVariant: websiteInfoData.products.selectVariant.en,
      minimumOrder: websiteInfoData.products.minimumOrder.en,
      materials: websiteInfoData.products.materials.en,
      specifications: websiteInfoData.products.specifications.en,
      loading: websiteInfoData.products.loading.en,
      notFound: websiteInfoData.products.notFound.en,
      noProducts: websiteInfoData.products.noProducts.en,
      categories: productCategoriesEn,
      collections: productCollectionsEn
    },
    services: {
      title: websiteInfoData.services.title.en,
      subtitle: websiteInfoData.services.subtitle.en,
      items: {
        custom: {
          title: websiteInfoData.services.items.custom.title.en,
          desc: websiteInfoData.services.items.custom.desc.en,
        },
        oem: {
          title: websiteInfoData.services.items.oem.title.en,
          desc: websiteInfoData.services.items.oem.desc.en,
        },
        quality: {
          title: websiteInfoData.services.items.quality.title.en,
          desc: websiteInfoData.services.items.quality.desc.en,
        }
      }
    },
    contact: {
      title: websiteInfoData.contact.title.en,
      subtitle: websiteInfoData.contact.subtitle.en,
      form: {
        name: websiteInfoData.contact.form.name.en,
        email: websiteInfoData.contact.form.email.en,
        message: websiteInfoData.contact.form.message.en,
        submit: websiteInfoData.contact.form.submit.en,
      },
      info: {
        addressLabel: websiteInfoData.contact.info.addressLabel.en,
        phoneLabel: websiteInfoData.contact.info.phoneLabel.en,
        faxLabel: websiteInfoData.contact.info.faxLabel.en,
        mobileLabel: websiteInfoData.contact.info.mobileLabel.en,
        qqLabel: websiteInfoData.contact.info.qqLabel.en,
        emailLabel: websiteInfoData.contact.info.emailLabel.en,
        websiteLabel: websiteInfoData.contact.info.websiteLabel.en,
        address: websiteInfoData.contact.info.address.en,
        phone: websiteInfoData.contact.info.phone.en,
        fax: websiteInfoData.contact.info.fax.en,
        mobile: websiteInfoData.contact.info.mobile.en,
        email: websiteInfoData.contact.info.email.en,
        website: websiteInfoData.contact.info.website.en,
        qq: websiteInfoData.contact.info.qq.en,
      },
      map: {
        googleMapSrc: websiteInfoData.contact.map.googleMapSrc,
        baiduMapUrl: websiteInfoData.contact.map.baiduMapUrl,
        baiduStaticImage: websiteInfoData.contact.map.baiduStaticImage,
        baiduAddressTitle: websiteInfoData.contact.map.baiduAddressTitle.en,
        baiduAddressDesc: websiteInfoData.contact.map.baiduAddressDesc.en,
        baiduButtonText: websiteInfoData.contact.map.baiduButtonText.en,
        overlayTitle: websiteInfoData.contact.map.overlayTitle.en,
        overlayDesc: websiteInfoData.contact.map.overlayDesc.en,
      }
    },
    footer: {
      rights: websiteInfoData.footer.rights.en,
    }
  },
  zh: {
    companyName: websiteInfoData.companyName.zh,
    metadata: {
      title: websiteInfoData.metadata.zh.title,
      description: websiteInfoData.metadata.zh.description,
    },
    nav: {
      productSearch: websiteInfoData.nav.productSearch.zh,
      home: websiteInfoData.nav.home.zh,
      about: websiteInfoData.nav.about.zh,
      products: websiteInfoData.nav.products.zh,
      services: websiteInfoData.nav.services.zh,
      contact: websiteInfoData.nav.contact.zh,
    },
    hero: {
      title: websiteInfoData.hero.title.zh,
      subtitle: websiteInfoData.hero.subtitle.zh,
      cta: websiteInfoData.hero.cta.zh,
      contact: websiteInfoData.hero.contact.zh,
      slides: {
        slide1: {
          title: websiteInfoData.hero.slides.slide1.title.zh,
          subtitle: websiteInfoData.hero.slides.slide1.subtitle.zh,
        },
        slide2: {
          title: websiteInfoData.hero.slides.slide2.title.zh,
          subtitle: websiteInfoData.hero.slides.slide2.subtitle.zh,
        },
        slide3: {
          title: websiteInfoData.hero.slides.slide3.title.zh,
          subtitle: websiteInfoData.hero.slides.slide3.subtitle.zh,
        },
        slide4: {
          title: websiteInfoData.hero.slides.slide4.title.zh,
          subtitle: websiteInfoData.hero.slides.slide4.subtitle.zh,
        }
      }
    },
    about: {
      title: websiteInfoData.about.title.zh,
      description: websiteInfoData.about.description.zh,
      mission: websiteInfoData.about.mission.zh,
      imageDesc: websiteInfoData.about.imageDesc.zh,
      stats: {
        years: websiteInfoData.about.stats.years.zh,
        markets: websiteInfoData.about.stats.markets.zh,
        quality: websiteInfoData.about.stats.quality.zh,
      }
    },
    facility: {
      title: websiteInfoData.facility.title.zh,
      subtitle: websiteInfoData.facility.subtitle.zh,
      features: {
        capacity: {
          title: websiteInfoData.facility.features.capacity.title.zh,
          desc: websiteInfoData.facility.features.capacity.desc.zh,
        },
        machinery: {
          title: websiteInfoData.facility.features.machinery.title.zh,
          desc: websiteInfoData.facility.features.machinery.desc.zh,
        },
        inspection: {
          title: websiteInfoData.facility.features.inspection.title.zh,
          desc: websiteInfoData.facility.features.inspection.desc.zh,
        },
      }
    },
    certifications: {
      title: websiteInfoData.certifications.title.zh,
      subtitle: websiteInfoData.certifications.subtitle.zh,
      items: certItemsZh
    },
    brands: {
      title: websiteInfoData.brands.title.zh,
      subtitle: websiteInfoData.brands.subtitle.zh,
      list: websiteInfoData.brands.list.zh
    },
    samples: {
      title: websiteInfoData.samples.title.zh,
      subtitle: websiteInfoData.samples.subtitle.zh,
      viewAll: websiteInfoData.samples.viewAll.zh,
      galleryTitle: websiteInfoData.samples.galleryTitle.zh
    },
    products: {
      title: websiteInfoData.products.title.zh,
      subtitle: websiteInfoData.products.subtitle.zh,
      searchButton: websiteInfoData.products.searchButton.zh,
      backToCategories: websiteInfoData.products.backToCategories.zh,
      backTo: websiteInfoData.products.backTo.zh,
      viewDetails: websiteInfoData.products.viewDetails.zh,
      inquire: websiteInfoData.products.inquire.zh,
      searchPlaceholder: websiteInfoData.products.searchPlaceholder.zh,
      showMore: websiteInfoData.products.showMore.zh,
      showLess: websiteInfoData.products.showLess.zh,
      selectVariant: websiteInfoData.products.selectVariant.zh,
      minimumOrder: websiteInfoData.products.minimumOrder.zh,
      materials: websiteInfoData.products.materials.zh,
      specifications: websiteInfoData.products.specifications.zh,
      loading: websiteInfoData.products.loading.zh,
      notFound: websiteInfoData.products.notFound.zh,
      noProducts: websiteInfoData.products.noProducts.zh,
      categories: productCategoriesZh,
      collections: productCollectionsZh
    },
    services: {
      title: websiteInfoData.services.title.zh,
      subtitle: websiteInfoData.services.subtitle.zh,
      items: {
        custom: {
          title: websiteInfoData.services.items.custom.title.zh,
          desc: websiteInfoData.services.items.custom.desc.zh,
        },
        oem: {
          title: websiteInfoData.services.items.oem.title.zh,
          desc: websiteInfoData.services.items.oem.desc.zh,
        },
        quality: {
          title: websiteInfoData.services.items.quality.title.zh,
          desc: websiteInfoData.services.items.quality.desc.zh,
        }
      }
    },
    contact: {
      title: websiteInfoData.contact.title.zh,
      subtitle: websiteInfoData.contact.subtitle.zh,
      form: {
        name: websiteInfoData.contact.form.name.zh,
        email: websiteInfoData.contact.form.email.zh,
        message: websiteInfoData.contact.form.message.zh,
        submit: websiteInfoData.contact.form.submit.zh,
      },
      info: {
        addressLabel: websiteInfoData.contact.info.addressLabel.zh,
        phoneLabel: websiteInfoData.contact.info.phoneLabel.zh,
        faxLabel: websiteInfoData.contact.info.faxLabel.zh,
        mobileLabel: websiteInfoData.contact.info.mobileLabel.zh,
        qqLabel: websiteInfoData.contact.info.qqLabel.zh,
        emailLabel: websiteInfoData.contact.info.emailLabel.zh,
        websiteLabel: websiteInfoData.contact.info.websiteLabel.zh,
        address: websiteInfoData.contact.info.address.zh,
        phone: websiteInfoData.contact.info.phone.zh,
        fax: websiteInfoData.contact.info.fax.zh,
        mobile: websiteInfoData.contact.info.mobile.zh,
        email: websiteInfoData.contact.info.email.zh,
        website: websiteInfoData.contact.info.website.zh,
        qq: websiteInfoData.contact.info.qq.zh,
      },
      map: {
        googleMapSrc: websiteInfoData.contact.map.googleMapSrc,
        baiduMapUrl: websiteInfoData.contact.map.baiduMapUrl,
        baiduStaticImage: websiteInfoData.contact.map.baiduStaticImage,
        baiduAddressTitle: websiteInfoData.contact.map.baiduAddressTitle.zh,
        baiduAddressDesc: websiteInfoData.contact.map.baiduAddressDesc.zh,
        baiduButtonText: websiteInfoData.contact.map.baiduButtonText.zh,
        overlayTitle: websiteInfoData.contact.map.overlayTitle.zh,
        overlayDesc: websiteInfoData.contact.map.overlayDesc.zh,
      }
    },
    chat: {
      title: websiteInfoData.chat.title.zh,
      greeting: websiteInfoData.chat.greeting.zh,
      askContact: websiteInfoData.chat.askContact.zh,
      finalResponse: websiteInfoData.chat.finalResponse.zh,
      form: {
        title: websiteInfoData.chat.form.title.zh,
        emailPlaceholder: websiteInfoData.chat.form.emailPlaceholder.zh,
        phonePlaceholder: websiteInfoData.chat.form.phonePlaceholder.zh,
        submitButton: websiteInfoData.chat.form.submitButton.zh,
      },
      inputPlaceholder: websiteInfoData.chat.inputPlaceholder.zh,
    },
    footer: {
      rights: websiteInfoData.footer.rights.zh,
    }
  }
};
